from parser import parse_directory
import json


results = parse_directory("./perceptive")

output = []

for document in results:
    content = []

    for page in document["pages"]:
        content.append(f"Page {page['page_number']}")

        content.append("Text:")
        content.append(page["text"])

        content.append(f"Tables found: {len(page['tables'])}")

        for table in page["tables"]:
            content.append(str(table["rows"]))

    output.append({
        "filename": document["filename"],
        "content": "\n".join(content)
    })


with open("parsed_output.json", "w", encoding="utf-8") as file:
    json.dump(output, file, indent=2, ensure_ascii=False)
