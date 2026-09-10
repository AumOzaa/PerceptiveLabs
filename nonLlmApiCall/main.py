from parser import parse_directory


results = parse_directory("./perceptive")

print(f"\nParsed {len(results)} PDFs")

for document in results:
    print(f"\n--- {document['filename']} ---")

    for page in document["pages"]:
        print(f"\nPage {page['page_number']}")

        print("Text:")
        print(page["text"])

        print(f"Tables found: {len(page['tables'])}")

        for table in page["tables"]:
            print(table["rows"])
