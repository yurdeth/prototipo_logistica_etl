from etl.load.grafo import cargar_grafo

if __name__ == "__main__":
    for tipo, filas in cargar_grafo().items():
        print(f"{tipo:12} {filas:>4} escritos")
