from pathlib import Path
import pymupdf


def parse_pdf(pdf_path: Path) -> dict:
    document = pymupdf.open(pdf_path)

    pages = []

    for page_number, page in enumerate(document, start=1):
        # 1. Extract normal text
        text = page.get_text()

        # 2. Detect tables
        table_finder = page.find_tables()

        tables = []

        for table in table_finder.tables:
            tables.append({
                "bbox": table.bbox,
                "rows": table.extract(),
            })

        pages.append({
            "page_number": page_number,
            "text": text,
            "tables": tables,
        })

    document.close()

    return {
        "filename": pdf_path.name,
        "pages": pages,
    }


def parse_directory(directory: str) -> list[dict]:
    directory_path = Path(directory)

    results = []

    for pdf_path in directory_path.glob("*.pdf"):
        print(f"Parsing: {pdf_path.name}")

        result = parse_pdf(pdf_path)

        results.append(result)

    return results
