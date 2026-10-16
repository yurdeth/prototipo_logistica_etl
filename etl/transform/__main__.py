from etl.transform.dimensiones import cargar_dimensiones

if __name__ == "__main__":
    for tabla, filas in cargar_dimensiones().items():
        print(f"{tabla:24} {filas:>7}")
