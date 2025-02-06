from gurobipy import Model, GRB, quicksum
import pandas as pd
import time
import os
import config

start = time.time() 


# ======================================================
# 1) Einlesen oder Erzeugen der Basis-Daten
# ======================================================

def modellierung_epex(szenario, strategie):
    cluster = int(szenario.split('_')[1])
    bidirektional = False if szenario.split('_')[10] == 'M' else True
    path = os.path.dirname(os.path.abspath(__file__))
    df_epex = pd.read_csv(os.path.join(path, 'input', 'epex_week.csv'), sep=';', decimal=',', index_col=0)
    df_lkw  = pd.read_csv(os.path.join(path, 'data', 'lkws', f'eingehende_lkws_loadstatus_{szenario}.csv'), sep=';', decimal=',', index_col=0)
    df_lkw.sort_values(by=['Ankunftszeit_total'], inplace=True)
    df_lkw.reset_index(drop=True, inplace=True)
    df_lkw_filtered = df_lkw[(df_lkw['LoadStatus'] == 1)][:807].copy()
    
    print(df_lkw_filtered)
    df_ladehub = pd.read_csv(os.path.join(path, 'data','konfiguration_ladehub',f'anzahl_ladesaeulen_{szenario}.csv'), sep=';', decimal=',')

    # Datenstruktur für den Lastgang
    df_lastgang = pd.DataFrame({
        'Zeit': [i for i in range(0, 525600, 5)] * 2,   # z.B. 8 Tage à 5-Min-Slots = 11520 Min
        'Leistung_Total': [0] * 105120 * 2,
        'Leistung_NCS': [0] * 105120 * 2,
        'Leistung_HPC': [0] * 105120 * 2,
        'Leistung_MCS': [0] * 105120 * 2
    })
    
    df_lastgang['Leistung_Total'] = df_lastgang['Leistung_Total'].astype(float)
    df_lastgang['Leistung_NCS'] = df_lastgang['Leistung_NCS'].astype(float)
    df_lastgang['Leistung_HPC'] = df_lastgang['Leistung_HPC'].astype(float)
    df_lastgang['Leistung_MCS'] = df_lastgang['Leistung_MCS'].astype(float)
    
    dict_lkw_lastgang = {
        'LKW_ID': [],
        'Ladetyp': [],
        'Zeit': [],
        'Ladezeit': [],
        'Leistung': [],
        'Pplus': [],
        'Pminus': [],
        'SOC': [],
        'X': [],
        'z': [],
        'Preis': []
    }

    # Maximale Leistung pro Ladesäulen-Typ
    ladeleistung = {
        'NCS': int(int(szenario.split('_')[7].split('-')[0])/100 * 100),
        'HPC': int(int(szenario.split('_')[7].split('-')[1])/100 * 350),
        'MCS': int(int(szenario.split('_')[7].split('-')[2])/100 * 1000)
    }

    # Verfügbare Anzahl Ladesäulen pro Typ
    max_saeulen = {
        'NCS': int(df_ladehub['NCS'][0]),
        'HPC': int(df_ladehub['HPC'][0]),
        'MCS': int(df_ladehub['MCS'][0])
    }
 
    netzanschlussfaktor = int(int(szenario.split('_')[5])/100)
    netzanschluss = (max_saeulen['NCS'] * ladeleistung['NCS'] + max_saeulen['HPC'] * ladeleistung['HPC'] + max_saeulen['MCS'] * ladeleistung['MCS']) * netzanschlussfaktor

    # Gesamter Zeit-Horizont (z.B. 8 Tage à 288 5-Min-Slots pro Tag)
    T = 288 * 365          # = 2304
    Delta_t = 5 / 60.0   # Zeitintervall in Stunden (5 Minuten)

    # ======================================================
    # 2) Schleife über die Ladestrategien
    # ======================================================
    # --------------------------------------------------
    # 2.1) LKW-Daten vorbereiten/filtern
    # --------------------------------------------------
    df_lkw_filtered['t_a'] = ((df_lkw_filtered['Ankunftszeit_total']) // 5).astype(int)
    df_lkw_filtered['t_d'] = ((df_lkw_filtered['Ankunftszeit_total'] + df_lkw_filtered['Pausenlaenge'] - 5) // 5).astype(int)
    t_in = df_lkw_filtered['t_a'].tolist()
    t_out = df_lkw_filtered['t_d'].tolist()
    l = df_lkw_filtered['Ladesäule'].tolist()
    SOC_A = df_lkw_filtered['SOC'].tolist()
    kapazitaet = df_lkw_filtered['Kapazitaet'].tolist()
    epex_price = df_epex['Preis'].tolist()
    
    SOC_req = []
    for index, row in df_lkw_filtered.iterrows():
        if row['Ladesäule'] == 'NCS':
            SOC_req.append(1)
            # SOC_req.append(4.5 * 1.26 * 80 / row['Kapazitaet'] + 0.15)
        else:
            SOC_req.append(4.5 * 1.26 * 80 / row['Kapazitaet'] + 0.15)
    
    E_req = [kapazitaet[i] * (SOC_req[i] - SOC_A[i]) for i in range(len(df_lkw_filtered))]
    I = len(df_lkw_filtered)
    
    # --------------------------------------------------
    # 2.2) Gurobi-Modell
    # --------------------------------------------------
    model = Model("Ladehub_Optimierung")
    # model.setParam('OutputFlag', 0)
    
    # --------------------------------------------------
    # 2.3) Variablen anlegen
    # --------------------------------------------------
    P = {}
    Pplus = {}
    Pminus = {}
    P_max_i = {}
    SoC = {}

    X = {}
    z = {}
    
    P = model.addVars([(i, t) for i in range(I) for t in range(t_in[i], t_out[i] + 1)], lb=-GRB.INFINITY if bidirektional else 0, vtype=GRB.CONTINUOUS, name="P")
    Pplus = model.addVars([(i, t) for i in range(I) for t in range(t_in[i], t_out[i] + 1)], lb=0, vtype=GRB.CONTINUOUS, name="Pplus")
    Pminus = model.addVars([(i, t) for i in range(I) for t in range(t_in[i], t_out[i] + 1)], lb=0, vtype=GRB.CONTINUOUS, name="Pminus")
    P_max_i = model.addVars([(i, t) for i in range(I) for t in range(t_in[i], t_out[i] + 1)], lb=0, vtype=GRB.CONTINUOUS, name="Pmax_i")
    X = model.addVars([(i, t) for i in range(I) for t in range(t_in[i], t_out[i] + 1)], vtype=GRB.BINARY, name="X")
    z = model.addVars([(i, t) for i in range(I) for t in range(t_in[i], t_out[i] + 1)], vtype=GRB.BINARY, name="z")
    SoC = model.addVars([(i, t) for i in range(I) for t in range(t_in[i], t_out[i] + 2)], lb=0, ub=1, vtype=GRB.CONTINUOUS, name="SoC")
    
    # for i in range(I):
    #     for t in range(t_in[i], t_out[i] + 1):
            
    #         if bidirektional:
    #             P[(i, t)] = model.addVar(lb=-GRB.INFINITY, vtype=GRB.CONTINUOUS)
    #         else:
    #             P[(i, t)] = model.addVar(lb=0, vtype=GRB.CONTINUOUS)
                
    #         Pplus[(i,t)] = model.addVar(lb = 0, vtype=GRB.CONTINUOUS)
    #         Pminus[(i,t)] = model.addVar(lb = 0, vtype=GRB.CONTINUOUS)
    #         P_max_i[(i,t)] = model.addVar(lb=0, vtype=GRB.CONTINUOUS, name=f"Pmax_{i}_{t}")

    #         X[(i, t)] = model.addVar(vtype=GRB.BINARY)
    #         z[(i,t)] = model.addVar(vtype=GRB.BINARY)
        
    #     for t in range(t_in[i], t_out[i] + 2):
    #         SoC[(i, t)] = model.addVar(lb=0, ub=1, vtype=GRB.CONTINUOUS, name=f"SoC_{i}_{t}")
    
    print('Variablen angelegt')
    # --------------------------------------------------
    # 2.5) Constraints
    # --------------------------------------------------
    
    # Begrenzung Anzahl Ladesäulen
    model.addConstrs((X[(i, t)] == 1 for i in range(I) for t in range(t_in[i], t_out[i] + 1)), name="X_equals_1")
    
    print('Constraint 0')
     
            
    for t in range(T):
        for typ in max_saeulen:
            relevant_i = [i for i in range(I) if l[i] == typ and (t_in[i] <= t <= t_out[i])]
            if len(relevant_i) > 0:
                model.addConstr(quicksum(X[(i, t)] for i in relevant_i) <= max_saeulen[typ],name=f"saeulen_{typ}_{t}")        
    print('Constraint 1')
    
    # Energiebedarf je LKW decken
    for i in range(I):
        model.addConstr(quicksum(P[(i, t)] * Delta_t for t in range(t_in[i], t_out[i] + 1)) == E_req[i])        
    print('Constraint 2')
    
    # Leistungsbegrenzung Ladekurve
    for i in range(I):
        model.addConstr(SoC[(i, t_in[i])] == SOC_A[i])
    for i in range(I):
        for t in range(t_in[i], t_out[i]+1):
            model.addConstr(SoC[(i, t+1)] == SoC[(i, t)] + (P[(i, t)] * Delta_t / kapazitaet[i]))
    xvals = [0.0, 0.5, 0.5, 0.8, 0.8, 1.0]
    yvals = [1000, 1000, 800, 800, 500, 500]
    for i in range(I):
        for t in range(t_in[i], t_out[i] + 1):
            model.addGenConstrPWL(SoC[(i, t)], P_max_i[(i, t)],xvals, yvals)
    for i in range(I):
        for t in range(t_in[i], t_out[i] + 1):
            model.addConstr(Pplus[(i,t)] <= P_max_i[(i,t)] * z[(i,t)]) 
            model.addConstr(Pminus[(i,t)] <= P_max_i[(i,t)] * (1-z[(i,t)]))
            # model.addConstr(Pplus[(i,t)] <= 3000 * z[(i,t)])
            # model.addConstr(Pminus[(i,t)] <= 3000 * (1-z[(i,t)]))
    print('Constraint 3')

    # Leistungsbegrenzung Ladesäulen-Typ    
    for i in range(I):
        typ = l[i]
        P_max_l = ladeleistung[typ]
        for t in range(t_in[i], t_out[i] + 1):
            model.addConstr(Pplus[(i,t)] <= z[(i,t)]     * P_max_l)
            model.addConstr(Pminus[(i,t)] <= (1-z[(i,t)]) * P_max_l)
            # model.addConstr(Pminus[(i,t)] <= (1-z[(i,t)]) * 3000)
            # model.addConstr(Pplus[(i,t)] <= z[(i,t)] * 3000)
    print('Constraint 4')
    
    # Leistungsbegrenzung Netzanschluss
    for t in range(T):
        model.addConstr(quicksum(Pplus[(i, t)] + Pminus[(i, t)] for i in range(I) if t_in[i] <= t <= t_out[i]) <= netzanschluss)    
    
    # Hilfsbedingungen
    for i in range(I):
        for t in range(t_in[i], t_out[i]+1):
            model.addConstr(P[(i,t)] == Pplus[(i,t)] - Pminus[(i,t)])
            
        for t in range(t_in[i], t_out[i]):
            model.addConstr(z[(i, t+1)] >= z[(i, t)])
    
    # --------------------------------------------------
    # 2.4) Zielfunktion
    # --------------------------------------------------
    
    if strategie == 'epex':
        obj_expr = quicksum(P[(i, t)] * epex_price[t] for i in range(I) for t in range(t_in[i], t_out[i] + 1))
        model.setObjective(obj_expr, GRB.MINIMIZE)
    elif strategie == 'Tmin':
        obj_expr = quicksum((t * Pplus[(i, t)]) - (t * Pminus[(i, t)]) for i in range(I) for t in range(t_in[i], t_out[i] + 1))
        model.setObjective(obj_expr, GRB.MINIMIZE)
    else:
        raise ValueError(f"Strategie {strategie} nicht bekannt.")

    # --------------------------------------------------
    # 2.6) Optimierung
    # --------------------------------------------------
    print('Starte Optimierung')
    model.optimize()
    
    # --------------------------------------------------
    # 2.7) Ergebnisse in df_lastgang übernehmen
    # --------------------------------------------------
    if model.Status == GRB.OPTIMAL:
        print(f"Optimale Lösung gefunden.")
        
        # for t in range(T):
        #     sum_p_total = 0
        #     sum_p_ncs = 0
        #     sum_p_hpc = 0
        #     sum_p_mcs = 0
        #     for i in range(I):
        #         if t_in[i] <= t <= t_out[i]:
        #             sum_p_total += P[(i, t)].X
        #             if l[i] == 'NCS':
        #                 sum_p_ncs += P[(i, t)].X
        #             elif l[i] == 'HPC':
        #                 sum_p_hpc += P[(i, t)].X
        #             elif l[i] == 'MCS':
        #                 sum_p_mcs += P[(i, t)].X
                
        #     df_lastgang.loc[(df_lastgang['Zeit'] == t*5),'Leistung_Total'] += sum_p_total
        #     df_lastgang.loc[(df_lastgang['Zeit'] == t*5),'Leistung_NCS'] += sum_p_ncs
        #     df_lastgang.loc[(df_lastgang['Zeit'] == t*5),'Leistung_HPC'] += sum_p_hpc
        #     df_lastgang.loc[(df_lastgang['Zeit'] == t*5),'Leistung_MCS'] += sum_p_mcs
                
        # for i in range(I):
        #     t_charging = 0
        #     for t in range(T):   
        #         if t_in[i] <= t <= t_out[i]+1:
        #             dict_lkw_lastgang['LKW_ID'].append(df_lkw_filtered.iloc[i]['Nummer'])
        #             dict_lkw_lastgang['Zeit'].append(t*5)
        #             dict_lkw_lastgang['Ladetyp'].append(l[i])
        #             dict_lkw_lastgang['Ladezeit'].append(t_charging)
        #             dict_lkw_lastgang['Preis'].append(epex_price[t])
        #             t_charging += 5
        #             if t > t_out[i]:
        #                 dict_lkw_lastgang['Leistung'].append(None)
        #                 dict_lkw_lastgang['Pplus'].append(None)
        #                 dict_lkw_lastgang['Pminus'].append(None)
        #                 dict_lkw_lastgang['SOC'].append(SoC[(i, t_out[i]+1)].X)
        #                 dict_lkw_lastgang['X'].append(None)
        #                 dict_lkw_lastgang['z'].append(None)
        #                 continue
        #             else:                        
        #                 dict_lkw_lastgang['X'].append(X[(i, t)].X)
        #                 dict_lkw_lastgang['z'].append(z[(i, t)].X)
        #                 dict_lkw_lastgang['Pplus'].append(Pplus[(i, t)].X)
        #                 dict_lkw_lastgang['Pminus'].append(Pminus[(i, t)].X)
        #                 dict_lkw_lastgang['Leistung'].append(P[(i, t)].X)
        #                 dict_lkw_lastgang['SOC'].append(SoC[(i, t)].X)
                    
                        
    else:
        print(f"Keine optimale Lösung für gefunden.")
    
    
    df_lkw_lastgang = pd.DataFrame(dict_lkw_lastgang)
    df_lkw_lastgang.sort_values(by=['LKW_ID', 'Zeit'], inplace=True)
    
    cost = (P[(i, t)].X * (5/60) * epex_price[t] for i in range(I) for t in range(t_in[i], t_out[i] + 1))
    total_cost = sum(cost)
    print(f"Total cost: {total_cost} € für Strategie {strategie}")
    
    return df_lastgang, df_lkw_lastgang

def main():
    df_lastgang_main = pd.DataFrame()
    df_lkw_lastgang_main = pd.DataFrame()
    
    strategies = ['epex', 'Tmin']
    
    for szenario in config.list_szenarien:
        for strategie in strategies:
            print(f"Optimierung EPEX: {szenario}")
            df_lastgang, df_lkw_lastgang = modellierung_epex(szenario, strategie)
            df_lastgang['Strategie'] = strategie
            df_lkw_lastgang['Strategie'] = strategie
            
            df_lastgang_main = pd.concat([df_lastgang_main, df_lastgang])
            df_lkw_lastgang_main = pd.concat([df_lkw_lastgang_main, df_lkw_lastgang])
            
        path = os.path.dirname(os.path.abspath(__file__)) 
        df_lastgang_main.to_csv(os.path.join(path, 'data', 'lastgang_epex', f'lastgang_{szenario}.csv'), sep=';', decimal=',', index=False) 
        df_lkw_lastgang_main.to_csv(os.path.join(path, 'data', 'lastgang_lkw_epex', f'lastgang_lkw_{szenario}.csv'), sep=';', decimal=',', index=False)
    
    
if __name__ == '__main__':
    start = time.time()
    main()
    end = time.time()
    
    print(f"Laufzeit: {end - start} Sekunden")
