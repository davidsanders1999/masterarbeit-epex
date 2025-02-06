from gurobipy import Model, GRB, quicksum
from gurobipy import GRB
import pandas as pd
import os
import time 
import config


def solve_minimum_stations(arrivals, departures, Q, max_values_per_day):
    """
    Minimiert die Anzahl benötigter Ladesäulen (y_s),
    um mindestens L LKWs zu bedienen.
    
    Parameter:
    ----------
    arrivals  : Liste mit Ankunftszeiten  a_i  (i = 0 .. n-1)
    departures: Liste mit Abfahrtszeiten  d_i  (i = 0 .. n-1)
    L         : Mindestens so viele LKWs müssen geladen werden
    Kmax      : Maximale Anzahl möglicher Ladesäulen
    
    Return:
    -------
    model       : Das aufgebaute und gelöste Gurobi-Modell
    x, y        : Variablen (Gurobi-Objekte) für LKW-Zuweisung (x) und Aktivierung (y)
    """
    
    # Anzahl LKWs
    n = len(arrivals)
    Kmax = int(max_values_per_day)
    L = Q * n
    
    # 1) Erstellen des Modells
    model = Model("Minimize_Stations")
    model.setParam('OutputFlag', 0)
    
    # 2) Variablen definieren
    # x[i,s] = 1, wenn LKW i auf Ladesäule s geladen wird
    x = model.addVars(n, Kmax, vtype=GRB.BINARY, name="x")
    
    # y[s] = 1, wenn Ladesäule s überhaupt aktiviert/genutzt wird
    y = model.addVars(Kmax, vtype=GRB.BINARY, name="y")
    
    # 3) Zielfunktion: Minimierung der Summe aktivierter Ladesäulen
    model.setObjective(quicksum(y[s] for s in range(Kmax)), GRB.MINIMIZE)
    
    # 4) Nebenbedingungen
    
    # (a) Mindestens L LKWs sollen geladen werden
    model.addConstr(quicksum(x[i, s] for i in range(n) for s in range(Kmax)) >= L,
                    name="MinLoadedTrucks")
    
    # (b) Jeder LKW darf höchstens auf 1 Ladesäule geladen werden
    model.addConstrs(
        (quicksum(x[i, s] for s in range(Kmax)) <= 1 for i in range(n)),
        name="OneStationPerTruck"
    )
    
    # (c) Eine LKW-Zuweisung ist nur erlaubt, wenn die Station aktiviert wurde
    model.addConstrs(
        (x[i, s] <= y[s] for i in range(n) for s in range(Kmax)),
        name="ActivateStation"
    )
    
    # (d) Zeitüberlappung: Überlappende LKWs können nicht dieselbe Säule belegen
    #    Overlap-Bedingung: zwei LKW i und j überlappen, wenn (a_i < d_j) und (a_j < d_i).
    for i in range(n):
        for j in range(i + 1, n):
            # Prüfen, ob sich Zeitintervalle [a_i, d_i) und [a_j, d_j) überlappen
            if arrivals[i] < departures[j] and arrivals[j] < departures[i]:
                # Überlappung => LKW i und j dürfen nicht gleichzeitig auf derselben Ladesäule sein
                for s in range(Kmax):
                    model.addConstr(x[i, s] + x[j, s] <= 1,
                                    name=f"Overlap_{i}_{j}_Station_{s}")
    
    # 5) Optimieren
    model.optimize()
    ladestatus = []
    
    
    # 6) Ergebnisse
    if model.Status == GRB.OPTIMAL:
        print(f"Optimales Objektiv: {model.ObjVal}")
        # Anzahl verwendeter Ladesäulen
        used_stations = sum(int(y[s].x) for s in range(Kmax))
        print(f"Anzahl benötigter Ladesäulen: {used_stations}")
        
        # Auswertung der Zuweisung
        loaded_trucks = 0
        for i in range(n):
            char = False
            for s in range(Kmax):
                if x[i, s].X > 0.5:
                    char = True
            if char:
                ladestatus.append(1)
                loaded_trucks += 1
            else:
                ladestatus.append(0)                    
                
        print(f"Geladene LKWs insgesamt: {loaded_trucks}")
        print(f"Ladequote: {loaded_trucks / n}")
    else:
        print("Keine optimale Lösung gefunden. Modellstatus:", model.Status)
    
    return ladestatus



def main():
    df_lkws = pd.DataFrame()
    
    ladetypen = ['HPC', 'MCS', 'NCS']
    
    list_szenarien = config.list_szenarien
    szenario = list_szenarien[0]
    
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    # df_anzahl_ladesaeulen = pd.read_csv(os.path.join(path, "konfiguration_ladehub", f"anzahl_ladesaeulen_{szenario}.csv"), sep=';', decimal=',', index_col=0)
    
    quote = {
        'NCS': 1,
        'HPC': 1,
        'MCS': 1
    }
        
    for ladetyp in ladetypen:
        print(f"Ladetyp: {ladetyp}")
        df_eingehende_lkws = pd.read_csv(os.path.join(path,'lkw_eingehend', 'eingehende_lkws_ladesaeule.csv'), sep=';', decimal=',', index_col=0)
        df_eingehende_lkws = df_eingehende_lkws[(df_eingehende_lkws['Cluster'] == 3) & (df_eingehende_lkws['Ladesäule'] == ladetyp)][:]
        arrival_times = df_eingehende_lkws['Ankunftszeit_total'].tolist()
        departure_times = (df_eingehende_lkws['Ankunftszeit_total'] + df_eingehende_lkws['Pausenlaenge']).tolist()
        max_values_per_day = df_eingehende_lkws.groupby(df_eingehende_lkws['Wochentag'])['Nummer'].count().max()
        
        ladestatus = solve_minimum_stations(arrival_times, departure_times, quote[ladetyp], max_values_per_day)
        df_eingehende_lkws['LoadStatus'] = ladestatus
        df_lkws = pd.concat([df_lkws, df_eingehende_lkws])
        
    df_lkws.to_csv(os.path.join(path, 'lkws', f'eingehende_lkws_loadstatus_{szenario}.csv'), sep=';', decimal=',')   

# -------------------------------------------------------
# Beispiel-Aufruf (bitte mit Ihren realen Daten ersetzen):
if __name__ == "__main__":
    time_start = time.time()
    main()
    time_end = time.time()
    print(f"Laufzeit: {time_end - time_start:.2f} Sekunden")