import pandas as pd
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
import os
import config
import time

def datenimport():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    df_eingehende_lkws = pd.read_csv(os.path.join(path,'lkw_eingehend', 'eingehende_lkws_ladesaeule.csv'), sep=';', decimal=',', index_col=0)
    return df_eingehende_lkws

def build_flow_network(df_filter, anzahl_ladesaeulen):
    """
    Baut ein Flussnetzwerk (DiGraph) für die gefilterten LKW (df_filter).
    - Jeder LKW bekommt zwei Knoten: LKW{i}_arr und LKW{i}_dep.
    - Diese werden an den Zeitknoten (5-Minuten-Raster) seiner Ankunfts- und Abfahrtszeit angeschlossen.
    - Zeitknoten sind miteinander verbunden mit Kapazität = anzahl_ladesaeulen.
    - SuperSource (S) -> LKW{i}_arr und LKW{i}_dep -> SuperSink (T) limitieren pro LKW den Fluss auf 1.
    """
    G = nx.DiGraph()

    # Super-Source und Super-Sink
    S = 'SuperSource'
    T = 'SuperSink'
    G.add_node(S)
    G.add_node(T)

    # Effektive Ankunft/Abfahrt (in Minuten) je nach Wochentag
    df_filter = df_filter.copy()
    df_filter['EffectiveArrival'] = df_filter['Ankunftszeit'] + (df_filter['Wochentag'] - 1) * 1440
    df_filter['EffectiveDeparture'] = df_filter['EffectiveArrival'] + df_filter['Pausenlaenge'] +5 # 5 Minuten Wechselzeit

    # Frühester Start und spätestes Ende, um Zeitknoten (5-Minuten-Raster) zu erzeugen
    start = int(df_filter['EffectiveArrival'].min())
    ende  = int(df_filter['EffectiveDeparture'].max())

    # Erstelle Zeitknoten im 5-Minuten-Schritt
    times = list(range(start, ende+1, 5))
    for t in times:
        G.add_node(f"time_{t}")
        
    # Kanten zwischen den Zeitknoten mit Kapazität = Anzahl Ladesäulen
    # Verbindung von SuperSource (S) zum ersten Zeitknoten
    G.add_edge(S, f"time_{times[0]}", capacity=anzahl_ladesaeulen, weight=0)

    # Verbindung vom letzten Zeitknoten zu SuperSink (T)
    G.add_edge(f"time_{times[-1]}", T, capacity=anzahl_ladesaeulen, weight=0)
    
    for i in range(len(times) - 1):
        u = f"time_{times[i]}"
        v = f"time_{times[i+1]}"
        G.add_edge(u, v, capacity=anzahl_ladesaeulen, weight=10)

    # Pro LKW: zwei Knoten + Kanten zu den Zeitknoten für Ankunft/Abfahrt
    for idx, row in df_filter.iterrows():
        lkw_id = row['Nummer']
        lkw_arr = f"LKW{lkw_id}_arr"
        lkw_dep = f"LKW{lkw_id}_dep"

        G.add_node(lkw_arr)
        G.add_node(lkw_dep)

        # Verknüpfen mit Zeitknoten (nur Ankunft/Abfahrt, wie gewünscht)
        arrival_node = f"time_{int(row['EffectiveArrival'])}"
        departure_node = f"time_{int(row['EffectiveDeparture'])}"

        G.add_edge(arrival_node, lkw_arr, capacity=1, weight=0)
        G.add_edge(lkw_dep, departure_node, capacity=1, weight=0)
        G.add_edge(lkw_arr, lkw_dep, capacity=1, weight=0)

        # # Drucke alle Kanten, bei denen mindestens ein LKW beteiligt ist
        # for u, v, data in G.edges(data=True):
        #     if 'LKW' in u or 'LKW' in v:
        #         print(f"Kante: {u} -> {v}, Kapazität: {data['capacity']}, Gewicht: {data['weight']}")
    
    print("Starte_Optimierung")
    flow_dict = nx.max_flow_min_cost(G, S, T)
    print("Optimierung_abgeschlossen")
    
    return flow_dict
    # return G, S, T

def konfiguration_ladehub(df_eingehende_lkws, szenario):
    """
    Hauptfunktion: Ermittelt pro Lade-Typ (HPC/MCS/NCS), wie viele Ladesäulen
    benötigt werden, um eine Ziel-Ladequote zu erreichen. Speichert zudem pro
    LKW, ob er letztlich geladen wurde (LoadStatus).
    """
    df_eingehende_lkws_loadstatus = pd.DataFrame()

    # Szenario-Einstellungen parsen
    cluster = int(szenario.split('_')[1])
    dict_ladequoten = {
        'NCS': float(szenario.split('_')[3].split('-')[0])/100,
        'HPC': float(szenario.split('_')[3].split('-')[1])/100,
        'MCS': float(szenario.split('_')[3].split('-')[2])/100
    }

    df_anzahl_ladesaeulen = pd.DataFrame(columns=['Cluster','NCS','Ladequote_NCS','HPC','Ladequote_HPC','MCS','Ladequote_MCS'])

    # Schleife über die verschiedenen Ladesäulen-Typen
    for ladetyp in dict_ladequoten:
        ladquote_ziel = dict_ladequoten[ladetyp]

        # Filtere passende LKW: richtiger Cluster + richtiger Ladesäulentyp
        df_eingehende_lkws_filter = df_eingehende_lkws[
            (df_eingehende_lkws['Cluster'] == cluster) &
            (df_eingehende_lkws['Ladesäule'] == ladetyp)
        ]

        ankommende_lkws     = len(df_eingehende_lkws_filter)
        ladequote           = 0
        anzahl_ladesaeulen  = 1

        # Wiederholung in Schritten bis zur Ziel-Ladequote
        for durchgang in range(ankommende_lkws):
            # Graphen via Node-Splitting-Ansatz aufbauen
            # G, S, T = build_flow_network(df_eingehende_lkws_filter, anzahl_ladesaeulen)
            flow_dict = build_flow_network(df_eingehende_lkws_filter, anzahl_ladesaeulen)

            # Max-Flow-Min-Cost
            # flow_dict = nx.max_flow_min_cost(G, S, T)

            # Bestimmen, wie viele LKW tatsächlich geladen wurden
            lkw_geladen = 0
            for idx, row in df_eingehende_lkws_filter.iterrows():
                # Prüfe, ob Fluss über LKW{i}_arr -> LKW{i}_dep > 0
                lkw_id = row['Nummer']
                lkw_arr = f"LKW{lkw_id}_arr"
                lkw_dep = f"LKW{lkw_id}_dep"
                flow_val = flow_dict.get(lkw_arr, {}).get(lkw_dep, None)
                if flow_val > 0:
                    lkw_geladen += 1

            # Ladequote berechnen
            ladequote = lkw_geladen / ankommende_lkws

            print(f"[{ladetyp}], Ladesäulen={anzahl_ladesaeulen}, Ladequote={ladequote}")

            # Falls Ziel-Ladequote erreicht/überschritten, LoadStatus speichern & Abbruch
            if ladequote >= ladquote_ziel:
                liste_lkw_status = []
                for idx, row in df_eingehende_lkws_filter.iterrows():
                    lkw_id = row['Nummer']
                    lkw_arr = f"LKW{lkw_id}_arr"
                    lkw_dep = f"LKW{lkw_id}_dep"
                    flow_of_this_truck = flow_dict.get(lkw_arr, {}).get(lkw_dep, 0)
                    if flow_of_this_truck > 0:
                        liste_lkw_status.append(1)
                    else:
                        liste_lkw_status.append(0)

                # LoadStatus-Spalte anhängen
                df_eingehende_lkws_filter = df_eingehende_lkws_filter.copy()
                df_eingehende_lkws_filter['LoadStatus'] = liste_lkw_status
                df_eingehende_lkws_loadstatus = pd.concat([df_eingehende_lkws_loadstatus, df_eingehende_lkws_filter])
                break

            # Sonst: Anzahl Ladesäulen anpassen und nächsten Durchgang
            # (Ein Minimalbeispiel, wie in Ihrem Code)
            if ladequote == 0:
                # falls gar keine LKW geladen, mindestens +1
                anzahl_ladesaeulen += 1
            else:
                # analog Ihrem bisherigen Ansatz
                anzahl_ladesaeulen = np.ceil(anzahl_ladesaeulen / ladequote * ladquote_ziel).astype(int)
                if anzahl_ladesaeulen == 0:
                    anzahl_ladesaeulen = 1

        # Speichern der Ergebnisse
        df_anzahl_ladesaeulen.loc[0,'Cluster'] = cluster
        df_anzahl_ladesaeulen.loc[0,ladetyp] = anzahl_ladesaeulen
        df_anzahl_ladesaeulen.loc[0,f'Ladequote_{ladetyp}'] = ladequote
    
    # Pfad für Dateien
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    
    # CSV: Anzahl Ladesäulen
    df_anzahl_ladesaeulen.to_csv(
        os.path.join(path, 'konfiguration_ladehub', f'anzahl_ladesaeulen_{szenario}.csv'),
        sep=';', decimal=','
    )

    # CSV: LKW mit LoadStatus
    df_eingehende_lkws_loadstatus.to_csv(
        os.path.join(path, 'lkws', f'eingehende_lkws_loadstatus_{szenario}.csv'),
        sep=';', decimal=','
    )
    
    return None

def main():
    df_eingehende_lkws = datenimport()
    
    for szenario in config.list_szenarien:
        print(f"Konfiguration Hub: {szenario}")
        konfiguration_ladehub(df_eingehende_lkws, szenario)

# -------------------------------------
# Hauptaufruf
# -------------------------------------

if __name__ == '__main__':
    main()