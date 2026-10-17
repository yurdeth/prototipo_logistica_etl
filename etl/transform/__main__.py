from etl.transform.dimensiones import cargar_dimensiones
from etl.transform.hechos import cargar_hechos

if __name__ == "__main__":
    for tabla, filas in {**cargar_dimensiones(), **cargar_hechos()}.items():
        print(f"{tabla:24} {filas:>7}")
