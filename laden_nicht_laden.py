import gurobipy as gp
from gurobipy import GRB
import pandas as pd
import os
import time 
import config

def max_truck_assignment(arrival_times, departure_times, num_stations):
    """
    Maximiert die Anzahl an LKWs, die bedient werden können, 
    unter der Einschränkung, dass LKWs sich nicht überlappen dürfen.

    Parameter:
    -----------
    arrival_times  : list of float
        Liste der Ankunftszeiten [a_i].
    departure_times: list of float
        Liste der Abfahrtszeiten [d_i].
    num_stations   : int
        Anzahl verfügbarer Ladesäulen (K).

    Returns:
    -----------
    model: gurobipy.Model
        Das aufgebaute und gelöste Gurobi-Modell.
    x: dict of gurobipy.Var
        Variablen x[i,s], bei denen x[i,s] = 1 bedeutet, 
        dass LKW i Ladesäule s zugeordnet wird.
    """

    # 1. Initialisierung des Modells
    model = gp.Model("max_truck_assignment")
    model.setParam('OutputFlag', 0)
    
    # 2. Indizes bestimmen
    trucks = range(len(arrival_times))  # i in I
    stations = range(num_stations)      # s in S

    # 3. Entscheidungsvariablen x[i,s]
    #    x[i,s] = 1, wenn LKW i auf Ladesäule s bedient wird, sonst 0
    x = model.addVars(
        [(i, s) for i in trucks for s in stations],
        vtype=GRB.BINARY,
        name="x"
    )

    # 4. Zielfunktion: Maximiere Anzahl der bedienten LKWs
    #    => Summe aller x[i,s]
    model.setObjective(
        gp.quicksum(x[i, s] for i in trucks for s in stations), 
        GRB.MAXIMIZE
    )

    # 5. Nebenbedingungen

    # (a) Jeder LKW darf höchstens einer Ladesäule zugewiesen werden
    for i in trucks:
        model.addConstr(
            gp.quicksum(x[i, s] for s in stations) <= 1, 
            name=f"Assign_LKW_{i}"
        )

    # (b) Zeitüberlappungskonflikte: 
    #     Wenn zwei LKWs i und j sich in ihren Zeitfenstern überlappen,
    #     dürfen sie nicht auf derselben Ladesäule sein.
    for i in trucks:
        for j in trucks:
            if i < j:  # Nur einmal prüfen, da i<j
                # Überlappen sich die Zeitfenster [a_i, d_i) und [a_j, d_j)?
                if (arrival_times[i] < departure_times[j]) and (arrival_times[j] < departure_times[i]):
                    # Dann dürfen LKW i und j nicht gleichzeitig auf derselben Säule sein
                    for s in stations:
                        model.addConstr(
                            x[i, s] + x[j, s] <= 1,
                            name=f"Overlap_{i}_{j}_s{s}"
                        )

    # 6. Optimierung starten
    model.optimize()
    ladestatus = []
    # 7. Ausgabe der Ergebnisse
    if model.status == GRB.OPTIMAL:
        print(f"Optimale Zielfunktion: {model.objVal}")
        # Ausgewählte Zuordnungen ausgeben
        for i in trucks:
            char = False
            for s in stations:
                if x[i, s].X > 0.5:
                    char = True
            if char:
                ladestatus.append(1)
            else:
                ladestatus.append(0)
        print(f'Ladequote: {sum(ladestatus)/len(ladestatus)}')
    else:
        print("Keine optimale Lösung gefunden. Status:", model.status)
    
    return ladestatus

def main():
    df_lkws = pd.DataFrame()
    
    ladetypen = ['HPC', 'MCS', 'NCS']
    
    list_szenarien = config.list_szenarien
    szenario = list_szenarien[0]
    
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    df_anzahl_ladesaeulen = pd.read_csv(os.path.join(path, "konfiguration_ladehub", f"anzahl_ladesaeulen_{szenario}.csv"), sep=';', decimal=',', index_col=0)
    
    anzahl = {
        'NCS': df_anzahl_ladesaeulen.loc[0, 'NCS'],
        'HPC': df_anzahl_ladesaeulen.loc[0, 'HPC'],
        'MCS': df_anzahl_ladesaeulen.loc[0, 'MCS']
    }
    
    for ladetyp in ladetypen:
        print(f"Ladetyp: {ladetyp}")
        df_eingehende_lkws = pd.read_csv(os.path.join(path,'lkw_eingehend', 'eingehende_lkws_ladesaeule.csv'), sep=';', decimal=',', index_col=0)
        df_eingehende_lkws = df_eingehende_lkws[(df_eingehende_lkws['Cluster'] == 2) & (df_eingehende_lkws['Ladesäule'] == ladetyp)][:]
        arrival_times = df_eingehende_lkws['Ankunftszeit_total'].tolist()
        departure_times = (df_eingehende_lkws['Ankunftszeit_total'] + df_eingehende_lkws['Pausenlaenge']).tolist()
        print(f"Anzahl LKWs: {len(arrival_times)}")
        ladestatus = max_truck_assignment(arrival_times, departure_times, anzahl[ladetyp])
        df_eingehende_lkws['LoadStatus'] = ladestatus
        df_lkws = pd.concat([df_lkws, df_eingehende_lkws])
        
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    df_lkws.to_csv(os.path.join(path, 'lkws', f'eingehende_lkws_loadstatus_{szenario}.csv'), sep=';', decimal=',')    
        

# Beispielaufruf (mit fiktiven Daten)
if __name__ == "__main__":
    # Beispiel-Daten: Ankunfts- und Abfahrtszeiten für 5 LKWs, 2 Ladesäulen

    time_start = time.time()
    main()
    time_end = time.time()
        
    print(f"Laufzeit: {time_end - time_start:.2f} Sekunden.")