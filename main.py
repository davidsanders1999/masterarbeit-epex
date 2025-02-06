import time
import zuweisung_ladetyp
import laden_nicht_laden
import konfiguration_ladehub
import epex_optimierung


time_start = time.time()

# zuweisung_ladetyp.main()
konfiguration_ladehub.main()
laden_nicht_laden.main()



time_end = time.time()
print(f'Laufzeit: {time_end - time_start} Sekunden')


# Maximale Laufzeit: 