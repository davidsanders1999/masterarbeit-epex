import time
import B_konfiguration_ladehub
import C_epex_optimierung
import A_zuweisung_ladetyp


time_start = time.time()

A_zuweisung_ladetyp.main()


time_end = time.time()
print(f'Laufzeit: {time_end - time_start} Sekunden')


# Maximale Laufzeit: 