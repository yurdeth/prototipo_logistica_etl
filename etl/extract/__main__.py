from etl.extract.extractor import extraer_todo

if __name__ == "__main__":
    for tabla, filas in extraer_todo().items():
        print(f"{tabla:24} {filas:>7} filas")
