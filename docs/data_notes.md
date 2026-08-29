
# Dataset Notes

The supplied workbook contains two sheets:

- `raw dataset`
- `cleaned dataset`

Nysa uses `cleaned dataset`, which contains 100 rows and these columns:

- Listing_ID
- year
- make
- model
- trim
- title
- description
- photo_url

There is no dedicated cash-price column in the workbook. Price and other vehicle facts are therefore extracted conservatively from the listing text. Missing facts are kept as null / "Not stated".

This is intentional: a grounded assistant should prefer an incomplete answer to a confident invented specification.
