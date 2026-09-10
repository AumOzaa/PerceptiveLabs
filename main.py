from fastapi import FastAPI, UploadFile, File, HTTPException
from pathlib import Path
import tempfile
import json
import os
import json
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from llama_parse import LlamaParse
from ollama import Client
from nonLlmApiCall.parser import parse_pdf

app = FastAPI()

load_dotenv()
@app.post("/parse-pdf")
async def parse_pdf_endpoint(file: UploadFile = File(...)):

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )

    # Create a temporary PDF file
    with tempfile.NamedTemporaryFile(
        suffix=".pdf",
        delete=False
    ) as temp_file:

        temp_file.write(await file.read())
        temp_pdf_path = Path(temp_file.name)

    try:
        # Use your existing parser
        parsed_document = parse_pdf(temp_pdf_path)

        content = []

        for page in parsed_document["pages"]:
            content.append(f"Page {page['page_number']}")
            content.append("Text:")
            content.append(page["text"])
            content.append(f"Tables found: {len(page['tables'])}")

            for table in page["tables"]:
                content.append(
                    json.dumps(
                        table["rows"],
                        ensure_ascii=False
                    )
                )

        response = {
            "filename": file.filename,
            "content": "\n".join(content)
        }

        return response

    finally:
        # Always delete the temporary PDF
        temp_pdf_path.unlink(missing_ok=True)

llama_parser = LlamaParse(
    api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
    result_type="markdown",
    verbose=True
)


# ==================================================
# OLLAMA CLOUD
# ==================================================

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")

if not OLLAMA_API_KEY:
    raise ValueError("OLLAMA_API_KEY not found in .env")


client = Client(
    host="https://ollama.com",
    headers={
        "Authorization": f"Bearer {OLLAMA_API_KEY}"
    }
)

MODEL_NAME = "gpt-oss:120b-cloud"


# ==================================================
# PASS 1 PROMPT
# ==================================================

PASS_1_PROMPT = """
You are a document information extraction system.

Your task is to analyze a bill or invoice and extract
EVERY identifiable piece of meaningful information present
in the document.

The bills may have completely different layouts,
structures, terminology, languages, and formats.

IMPORTANT RULES:

1. Do NOT assume a predefined invoice schema.

2. Do NOT decide whether an attribute is important or
   unimportant. Extract it anyway.

3. Do NOT remove unusual or uncommon attributes.

4. Do NOT normalize attribute names.
   Preserve the original terminology used in the document.

5. Do NOT hallucinate information.

6. Do NOT infer values that are not explicitly present.

7. If information is unclear or unreadable, do not guess.

8. Preserve values exactly wherever possible.

9. Preserve numbers, dates, invoice numbers, tax numbers,
   identifiers, percentages, quantities and monetary values
   accurately.

10. Extract information from ALL parts of the document,
    including headers, body, tables, totals, footers,
    notes, payment information and terms.

11. Extract ALL line items from item/product/service tables.

12. For line items, preserve every identifiable column/value,
    such as item name, description, quantity, rate, unit,
    discount, tax, amount, SKU, HSN, etc.

13. If the same type of information appears multiple times,
    preserve each occurrence when it represents different
    information.

14. Do not combine separate values unless the document itself
    clearly treats them as one value.

15. Keep the original spelling and terminology of labels.

For every discovered attribute, return:

- name:
    The original label/name used in the document.

- value:
    The extracted value.

- category:
    A broad organizational category.

- context:
    Where the attribute appeared in the document.

- evidence:
    The relevant text from the document that supports
    the extracted value.

Possible categories include:

- document
- seller
- buyer
- item
- tax
- payment
- financial
- shipping
- contact
- address
- banking
- regulatory
- other

These categories are only organizational hints.
Do not force an attribute into an incorrect category.

For line items, represent each identifiable value as an
attribute and use the context to identify the corresponding
line item.

Example:

{
    "attributes": [
        {
            "name": "Invoice No.",
            "value": "INV-12345",
            "category": "document",
            "context": "invoice header",
            "evidence": "Invoice No.: INV-12345"
        },
        {
            "name": "GSTIN",
            "value": "24ABCDE1234F1Z5",
            "category": "seller",
            "context": "seller information",
            "evidence": "GSTIN: 24ABCDE1234F1Z5"
        },
        {
            "name": "CGST",
            "value": "125.50",
            "category": "tax",
            "context": "tax summary",
            "evidence": "CGST: 125.50"
        }
    ]
}

The example is only an illustration.

Your actual output must contain ALL meaningful
attributes found in the provided document.

Return ONLY valid JSON.
"""


# ==================================================
# PASS 2 PROMPT
# ==================================================

PASS_2_PROMPT = """
You are a bill and invoice data normalization system.

You will receive the RAW JSON extracted from a bill or invoice
by a previous extraction stage.

The previous stage intentionally extracted as much information
as possible.

Your task is to transform that raw extraction into the FINAL JSON
that contains ONLY important and meaningful information from the
bill.

==================================================
PRIMARY OBJECTIVE
==================================================

Produce a clean, consistent, machine-readable JSON containing
the important values from the bill.

The final JSON must NOT contain extraction metadata.

Do NOT output:
- raw_name
- canonical_name
- importance
- category
- context
- evidence
- explanations
- reasoning

The keys in the final JSON must directly represent the
normalized attributes and their values.

==================================================
IMPORTANT RULES
==================================================

1. ONLY use information present in the RAW JSON.

2. NEVER invent, infer, or hallucinate values.

3. Remove information that is:
   - decorative
   - redundant
   - irrelevant
   - formatting-related
   - meaningless business-wise
   - duplicated without adding information

4. Keep information that is useful for:
   - identifying the bill
   - identifying the seller
   - identifying the buyer/customer
   - identifying purchased products/services
   - understanding quantities and prices
   - understanding taxes
   - understanding payment information
   - understanding financial totals
   - accounting
   - tracking or processing the transaction

5. Do NOT remove an attribute simply because it appears
   only once or is uncommon.

6. Different bills can contain different attributes.
   Do NOT force every bill to contain the same fields.

7. Do NOT create null, empty, or placeholder fields for
   information that does not exist.

==================================================
NORMALIZATION
==================================================

Different labels that clearly represent the same concept
must use the SAME canonical field name.

Examples:

"Bill No."
"Invoice No."
"Invoice Number"
"Tax Invoice No."
"Inv. No."

→ "invoice_number"


"Invoice Date"
"Bill Date"
"Date of Invoice"

→ "invoice_date"


"Customer"
"Customer Name"
"Buyer"
"Buyer Name"

→ "buyer_name"


"Supplier"
"Seller"
"Vendor"
"Supplier Name"

→ "seller_name"


"GSTIN"
"GST No."
"GST Number"
"GST Identification Number"

→ "gstin"


"Bank"
"Bank Name"

→ "bank_name"


"Total"
"Grand Total"
"Net Payable"
"Amount Payable"

→ Use the most semantically appropriate canonical field
based on the context. Do NOT automatically assume they
are identical.


"Qty"
"Quantity"

→ "quantity"


"Rate"
"Unit Price"
"Price/Unit"

→ "unit_price"


"Amount"
"Line Total"
"Item Amount"

→ "amount"

Use concise machine-readable names.

Use snake_case.

==================================================
DOCUMENT INFORMATION
==================================================

When present, preserve important document information such as:

- invoice number
- invoice date
- due date
- purchase order number
- reference number
- IRN
- e-way bill number
- place of supply
- currency

Example:

{
    "document": {
        "invoice_number": "INV-1023",
        "invoice_date": "10/09/2026",
        "irn": "646d19e7047653731668d2db7300e05b9fa86b3f0043c258debc89dff64c59b4"
    }
}

==================================================
SELLER INFORMATION
==================================================

Preserve important seller information when present:

- seller name
- GSTIN
- tax identification number
- address
- phone
- email
- bank name
- other important seller identifiers

Example:

{
    "seller": {
        "name": "ABC Electronics",
        "gstin": "24ABCDE1234F1Z5",
        "address": "Ahmedabad, Gujarat"
    }
}

Do not create a field merely because it is listed above.
Only include fields actually present in the RAW JSON.

==================================================
BUYER INFORMATION
==================================================

Preserve important buyer/customer information when present:

- buyer name
- GSTIN
- tax identification number
- address
- phone
- email
- customer/account identifier

Example:

{
    "buyer": {
        "name": "XYZ Pvt Ltd",
        "gstin": "24XYZDE5678F1Z5",
        "address": "Ahmedabad, Gujarat"
    }
}

==================================================
LINE ITEMS
==================================================

Preserve important information for EVERY line item.

Represent each line item as a separate object inside
the "items" array.

Possible fields include:

- description
- product_name
- item_code
- sku
- hsn
- sac
- quantity
- unit
- unit_price
- discount
- tax_rate
- tax_amount
- amount

Do NOT create fields that are not present.

Example:

{
    "items": [
        {
            "description": "Laptop",
            "quantity": 2,
            "unit_price": 50000,
            "amount": 100000
        }
    ]
}

If a bill has 10 line items, preserve all 10.

==================================================
TAX INFORMATION
==================================================

Preserve important tax information.

Examples:

- CGST
- SGST
- IGST
- VAT
- tax rate
- taxable amount
- total tax

Normalize names where appropriate.

Examples:

"CGST Amount"
"CGST"

→ "cgst"

"SGST Amount"
"SGST"

→ "sgst"

"IGST Amount"
"IGST"

→ "igst"

Do NOT combine separate tax components when they are
separately provided.

==================================================
FINANCIAL INFORMATION
==================================================

Preserve important financial values such as:

- subtotal
- taxable amount
- discount
- shipping charges
- other charges
- tax amount
- round off
- grand total
- amount paid
- balance due
- currency

Use the semantic meaning of the value rather than simply
the original label.

For example:

"Grand Total"
"Total Amount"
"Net Amount"

may represent different concepts depending on the bill.

Analyze the context before normalizing them.

==================================================
PAYMENT INFORMATION
==================================================

Preserve important payment information when present:

- payment method
- payment terms
- bank name
- account information
- transaction/reference number
- payment status

Example:

{
    "payment": {
        "payment_method": "Bank Transfer",
        "bank_name": "Axis Bank",
        "transaction_reference": "TXN12345"
    }
}

==================================================
OTHER IMPORTANT INFORMATION
==================================================

If an important attribute does not naturally belong in
document, seller, buyer, items, tax, financial, or payment,
you may place it inside:

"other"

Example:

{
    "other": {
        "delivery_date": "12/09/2026"
    }
}

Only use "other" when the information is genuinely
meaningful and does not fit another category.

==================================================
DATA ACCURACY
==================================================

Preserve extracted values accurately.

Do NOT change the meaning of values.

Do NOT guess unclear values.

Preserve numerical precision when available.

If the raw extraction contains:

"120360.50"

do not arbitrarily change it to:

"120361"

If a monetary value clearly represents a number,
prefer a numeric JSON value rather than a string.

Example:

"grand_total": 120360.50

However, if the value contains meaningful non-numeric
information or its numeric interpretation is uncertain,
preserve it as a string.

==================================================
FINAL JSON FORMAT
==================================================

The following is an EXAMPLE structure, not a mandatory
schema.

Only include sections and fields that actually exist
and are important.

Example:

{
    "document": {
        "invoice_number": "INV-1023",
        "invoice_date": "10/09/2026",
        "due_date": "25/09/2026"
    },

    "seller": {
        "name": "ABC Electronics",
        "gstin": "24ABCDE1234F1Z5",
        "address": "Ahmedabad, Gujarat"
    },

    "buyer": {
        "name": "XYZ Pvt Ltd",
        "gstin": "24XYZDE5678F1Z5"
    },

    "items": [
        {
            "description": "Laptop",
            "quantity": 2,
            "unit_price": 50000,
            "amount": 100000
        }
    ],

    "tax": {
        "cgst": 9180,
        "sgst": 9180,
        "total_tax": 18360
    },

    "financial": {
        "subtotal": 102000,
        "discount": 0,
        "grand_total": 120360,
        "currency": "INR"
    },

    "payment": {
        "payment_method": "Bank Transfer",
        "bank_name": "Axis Bank"
    }
}

Again, this is only an example.

A particular bill may contain many more fields or far fewer
fields.

==================================================
STRICT OUTPUT REQUIREMENT
==================================================

Return ONLY valid JSON.

Do not return Markdown.

Do not return code fences.

Do not return explanations.

Do not return comments.

Do not return metadata about the extraction.

The final JSON must contain only:

    normalized_field_name: value

or appropriate nested objects/arrays containing:

    normalized_field_name: value

The final output is intended to be directly consumed
by another program.
"""


# ==================================================
# PARSE LLM
# ==================================================

@app.post("/parse-llm")
async def parse_llm(file: UploadFile = File(...)):

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )

    temp_pdf_path = None

    try:

        # ------------------------------------------
        # 1. Save uploaded PDF temporarily
        # ------------------------------------------

        with tempfile.NamedTemporaryFile(
            suffix=".pdf",
            delete=False
        ) as temp_file:

            temp_file.write(await file.read())
            temp_pdf_path = Path(temp_file.name)


        # ------------------------------------------
        # 2. LlamaParse
        # ------------------------------------------

        documents = llama_parser.load_data(
            str(temp_pdf_path)
        )

        document_text = ""

        for document in documents:
            document_text += document.text
            document_text += "\n\n"


        if not document_text.strip():
            raise HTTPException(
                status_code=422,
                detail="LlamaParse returned an empty document"
            )


        # ------------------------------------------
        # 3. Ollama - Pass 1
        # ------------------------------------------

        response = client.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": PASS_1_PROMPT
                },
                {
                    "role": "user",
                    "content": (
                        "Extract every identifiable attribute "
                        "from the following bill/invoice.\n\n"
                        "DOCUMENT:\n\n"
                        + document_text
                    )
                }
            ],
            format="json"
        )


        raw_result = response["message"]["content"]

        raw_json = json.loads(raw_result)


        # ------------------------------------------
        # 4. Convert Pass 1 JSON to text
        # ------------------------------------------

        raw_text = json.dumps(
            raw_json,
            ensure_ascii=False,
            indent=2
        )


        # ------------------------------------------
        # 5. Ollama - Pass 2
        # ------------------------------------------

        response = client.chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": PASS_2_PROMPT
                },
                {
                    "role": "user",
                    "content": (
                        "Normalize and clean the following "
                        "raw bill extraction.\n\n"
                        "RAW EXTRACTION:\n\n"
                        + raw_text
                    )
                }
            ],
            format="json"
        )


        final_result = response["message"]["content"]


        # ------------------------------------------
        # 6. Validate final JSON
        # ------------------------------------------

        final_json = json.loads(final_result)


        # ------------------------------------------
        # 7. Return final JSON
        # ------------------------------------------

        return final_json


    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="Ollama returned invalid JSON"
        )


    except HTTPException:
        raise


    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


    finally:

        # ------------------------------------------
        # 8. Delete temporary PDF
        # ------------------------------------------

        if temp_pdf_path:
            temp_pdf_path.unlink(missing_ok=True)
