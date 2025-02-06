# ======================================================
# Importing Required Libraries
# ======================================================
import pandas as pd
import numpy as np
import os

np.random.seed(42)

# ======================================================
# Main Function
# ======================================================
def main():
    """
    Main function to execute the truck simulation pipeline.
    """
    # Load configurations and data
    config = load_configurations()
    df_verteilungsfunktion, df_ladevorgaenge_daily = load_input_data(config['path'])

    # Generate truck data
    df_lkws = generate_truck_data(config, df_verteilungsfunktion, df_ladevorgaenge_daily)

    # Assign charging stations
    df_lkws = assign_charging_stations(df_lkws, config)

    # Add datetime and export results
    finalize_and_export_data(df_lkws, config)

    # Analyze charging types
    analyze_charging_types(df_lkws)

# ======================================================
# Configuration and Input Data
# ======================================================
def load_configurations():
    """
    Load and return the configurations for the simulation.
    """
    path = os.path.dirname(os.path.abspath(__file__))
    freq = 5  # Frequency of updates (in minutes)
    return {
        'path': path,
        'freq': freq,
        'kapazitaeten_lkws': {
            '600': 0.093,
            '720': 0.187,
            '840': 0.289,
            '960': 0.431
        },
        'pausentypen': ['Schnelllader', 'Nachtlader'],
        'pausenzeiten_lkws': {
            'Schnelllader': 45,
            'Nachtlader': 540
        },
        'leistung': {'HPC': 350, 'NCS': 100, 'MCS': 1000},
        'max_leistung_lkw': 1000,
        'energie_pro_abschnitt': 80 * 4.5 * 1.26,
        'sicherheitspuffer': 0.15
    }

def load_input_data(path):
    """
    Load input data from CSV files.
    """
    df_verteilungsfunktion = pd.read_csv(
        os.path.join(path, 'input/verteilungsfunktion_mcs-ncs.csv'), sep=','
    )
    df_ladevorgaenge_daily = pd.read_csv(
        os.path.join(path, 'input/ladevorgaenge_daily_cluster.csv'), sep=';', decimal=','
    )
    return df_verteilungsfunktion, df_ladevorgaenge_daily

# ======================================================
# Helper Functions
# ======================================================
def get_soc(ankunftszeit):
    """
    Calculate the State of Charge (SOC) based on arrival time.
    """
    if ankunftszeit < 360:  # Early morning  #TODO: Prüfen, ob 360 korrekt ist
        soc = 0.2 + np.random.uniform(-0.1, 0.1)
    else:
        soc = -(0.00028) * ankunftszeit + 0.6
        soc += np.random.uniform(-0.1, 0.1)
    return soc

def get_leistungsfaktor(soc):
    """
    Adjust power factor based on SOC.
    """
    if soc <= 1:
        return 1
    elif soc < 0.9:
        return 0.8
    else:
        return 0.6 if soc < 1 else 0.2

# ======================================================
# Truck Data Generation
# ======================================================
def generate_truck_data(config, df_verteilungsfunktion, df_ladevorgaenge_daily):
    """
    Generate truck data based on the input configurations.
    """
    dict_lkws = {
        'Cluster': [],
        'Wochentag': [],
        'Ankunftszeit': [],
        'Nummer': [],
        'Pausentyp': [],
        'Kapazitaet': [],
        'Max_Leistung': [],
        'SOC': [],
        'Pausenlaenge': []
    }

    for cluster_id in range(1, 4):  # Loop through clusters
        for day in range(364):  # Loop through days
            
            anzahl_lkws = {
                pausentyp: df_ladevorgaenge_daily[(df_ladevorgaenge_daily['Cluster'] == cluster_id) & (df_ladevorgaenge_daily['Wochentag'] == day % 7 + 1) & (df_ladevorgaenge_daily['Ladetype'] == pausentyp)]['Anzahl'].values[0]
                for pausentyp in config['pausentypen']
            }
            for pausentyp in config['pausentypen']:  # Loop through break types
                for _ in range(int(anzahl_lkws[pausentyp])):
                    pausenzeit = config['pausenzeiten_lkws'][pausentyp]
                    kapazitaet = np.random.choice(
                        list(config['kapazitaeten_lkws'].keys()),
                        p=list(config['kapazitaeten_lkws'].values())
                    )
                    minuten = np.random.choice(
                        df_verteilungsfunktion['Zeit'],
                        p=df_verteilungsfunktion[pausentyp]
                    )
                    soc = get_soc(minuten)
                    dict_lkws['Cluster'].append(cluster_id)
                    dict_lkws['Wochentag'].append(day + 1)
                    dict_lkws['Kapazitaet'].append(kapazitaet)
                    dict_lkws['Max_Leistung'].append(config['max_leistung_lkw'])
                    dict_lkws['Nummer'].append(None)  # Placeholder for ID
                    dict_lkws['SOC'].append(soc)
                    dict_lkws['Pausentyp'].append(pausentyp)
                    dict_lkws['Pausenlaenge'].append(pausenzeit)
                    dict_lkws['Ankunftszeit'].append(minuten)

    df_lkws = pd.DataFrame(dict_lkws)
    df_lkws.sort_values(by=['Cluster', 'Wochentag', 'Ankunftszeit'], inplace=True)
    df_lkws.reset_index(drop=True, inplace=True)
    df_lkws['Nummer'] = df_lkws.groupby('Cluster').cumcount() + 1
    df_lkws['Nummer'] = df_lkws['Nummer'].apply(lambda x: f'{x:04}')
    return df_lkws

# ======================================================
# Assign Charging Stations
# ======================================================
def assign_charging_stations(df_lkws, config):
    """
    Assign charging stations to each truck based on configurations.
    """
    df_lkws['Ladesäule'] = None
    for index in range(len(df_lkws)):
        kapazitaet = float(df_lkws.loc[index, 'Kapazitaet'])
        soc_init = df_lkws.loc[index, 'SOC']
        pausentyp = df_lkws.loc[index, 'Pausentyp']
        pausenzeit = df_lkws.loc[index, 'Pausenlaenge']
        soc_target = config['energie_pro_abschnitt'] / kapazitaet + config['sicherheitspuffer']

        if pausentyp == 'Nachtlader':
            df_lkws.loc[index, 'Ladesäule'] = 'NCS'
            continue
        
        if soc_target < soc_init:
            raise ValueError("Error: Target SOC is less than initial SOC!")

        ladezeiten = {}

        for station, leistung_init in config['leistung'].items():
            ladezeit = 0
            soc = soc_init
            while soc < soc_target:
                ladezeit += config['freq']
                leistungsfaktor = get_leistungsfaktor(soc)
                aktuelle_leistung = min(leistung_init, leistungsfaktor * config['max_leistung_lkw'])
                energie = aktuelle_leistung * config['freq'] / 60
                soc += energie / kapazitaet
            ladezeiten[station] = pausenzeit - ladezeit

        if ladezeiten['HPC'] >= 0:
            df_lkws.loc[index, 'Ladesäule'] = 'HPC'
        elif ladezeiten['MCS'] >= 0:
            df_lkws.loc[index, 'Ladesäule'] = 'MCS'
    return df_lkws

# ======================================================
# Finalize and Export Data
# ======================================================
def finalize_and_export_data(df_lkws, config):
    """
    Finalize the DataFrame, add datetime, and export to a CSV file.
    """
    df_lkws['Zeit_DateTime'] = pd.to_datetime(
        df_lkws['Ankunftszeit'] + ((df_lkws['Wochentag'] - 1) * 1440),
        unit='m',
        origin='2021-01-01'
    )
    df_lkws['Ankunftszeit_total'] = df_lkws['Ankunftszeit'] + ((df_lkws['Wochentag'] - 1) * 1440)
    df_lkws.to_csv(
        os.path.join(config['path'], 'data', 'lkw_eingehend', 'eingehende_lkws_ladesaeule.csv'),
        sep=';', decimal=','
    )

# ======================================================
# Analyze Charging Types
# ======================================================
def analyze_charging_types(df_lkws):
    """f
    Analyze and print the proportion of each charging type.
    """
    df_ladetypen = df_lkws.groupby('Ladesäule').size().reset_index(name='Anzahl')
    print(df_ladetypen)

# ======================================================
# Main Execution
# ======================================================
if __name__ == "__main__":
    main()