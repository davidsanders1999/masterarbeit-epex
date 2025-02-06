# Allgemeine Annahmen

szenario = 'base_2'
freq = 5
wartezeit = 15
# ladegrenze = 0.8
netzanschlussfaktor = 0.3

# Definition "Vollständige Ladung"
energie_pro_abschnitt = 80 * 4.5 * 1.26
sicherheitspuffer = 0.15


# Szenarien
simulationsfokus = ['Cluster', 'Ladequoten', 'Netzanschluss', 'Leistung', 'Pausenzeiten']
# fokus = simulationsfokus[1]

# Clustervariation
cluster             = [1, 2, 3]

# Ladequotenvariation             
ladequote_HPC       = [0.4, 0.7, 1] 
ladequote_MCS       = [0.4, 0.7, 1] 
ladequote_NCS       = [0.4, 0.7, 1]  

# Netzanschlussvariation
netzanschlussfaktor = [0.1, 0.2, 0.3, 0.4, 1]

# Leistungsvariation
leistung_hpc        = [0.8, 1, 1.5]
leistung_mcs        = [0.8, 1, 1.5]
leistung_ncs        = [0.8, 1, 1.2]

# Pausenzeiten
pausen_schnell      = [45, 60, 75]
pausen_nacht    = [540, 600, 660]

# ======================================================
list_szenarien = [
# 'cl_2_quote_100-100-100_netz_100_pow_100-100-100_pause_45-540_M', # Base
    
# 'cl_1_quote_100-100-100_netz_100_pow_100-100-100_pause_45-540_M', # Cluster 
# 'cl_3_quote_100-100-100_netz_100_pow_100-100-100_pause_45-540_M',
 
# 'cl_2_quote_40-100-100_netz_100_pow_100-100-100_pause_45-540_M', # Ladequoten
# 'cl_2_quote_70-100-100_netz_100_pow_100-100-100_pause_45-540_M', 
# 'cl_2_quote_100-40-100_netz_100_pow_100-100-100_pause_45-540_M', 
# 'cl_2_quote_100-70-100_netz_100_pow_100-100-100_pause_45-540_M', 
# 'cl_2_quote_100-100-40_netz_100_pow_100-100-100_pause_45-540_M', 
# 'cl_2_quote_100-100-70_netz_100_pow_100-100-100_pause_45-540_M',

# 'cl_2_quote_100-100-100_netz_10_pow_100-100-100_pause_45-540_M', # Netzanschluss
# 'cl_2_quote_100-100-100_netz_20_pow_100-100-100_pause_45-540_M', 
# 'cl_2_quote_100-100-100_netz_30_pow_100-100-100_pause_45-540_M', 
# 'cl_2_quote_100-100-100_netz_40_pow_100-100-100_pause_45-540_M',

# 'cl_2_quote_100-100-100_netz_100_pow_90-100-100_pause_45-540_M', # Leistung
# 'cl_2_quote_100-100-100_netz_100_pow_100-50-100_pause_45-540_M',
# 'cl_2_quote_100-100-100_netz_100_pow_100-100-50_pause_45-540_M',
# 'cl_2_quote_100-100-100_netz_100_pow_110-100-100_pause_45-540_M',
# 'cl_2_quote_100-100-100_netz_100_pow_100-150-100_pause_45-540_M',
# 'cl_2_quote_100-100-100_netz_100_pow_100-100-150_pause_45-540_M',

# 'cl_2_quote_100-100-100_netz_100_pow_100-100-100_pause_60-540_M', # Pausenzeiten
# 'cl_2_quote_100-100-100_netz_100_pow_100-100-100_pause_75-540_M',
# 'cl_2_quote_100-100-100_netz_100_pow_100-100-100_pause_45-600_M',
# 'cl_2_quote_100-100-100_netz_100_pow_100-100-100_pause_45-660_M', 

'cl_2_quote_100-100-100_netz_100_pow_100-100-100_pause_45-540_B', # Bidirektional 
]