import io

from PIL import Image
from schwifty import IBAN
from segno import helpers
import fitz
import xmltodict

from girocode.util import ENV


"""
Documentation:
https://github.com/pymupdf/PyMuPDF/issues/1017
https://segno.readthedocs.io/en/latest/epc-qrcodes.html
https://segno.readthedocs.io/en/latest/api.html
https://pymupdf.readthedocs.io/en/latest/page.html
https://github.com/martinblech/xmltodict
"""


def create_girocode(reference, amount, **kwargs):
    # Invoking the constructor will make sure
    # that the IBAN and checksum is valid.
    iban = IBAN(ENV('GIROCODE_RECIPIENT_IBAN'))
    qrcode = helpers.make_epc_qr(
        name=ENV('GIROCODE_RECIPIENT_NAME'),
        iban=iban.compact,
        text=ENV('GIROCODE_TEXT_FORMAT').format(reference=reference),
        amount=amount,
        encoding='UTF-8',
        **kwargs
    )
    out = io.BytesIO()
    qrcode.save(
        out=out,
        kind='png',
        scale=ENV('GIROCODE_QR_SCALE', to=int),
        border=ENV('GIROCODE_QR_BORDER', to=int)
    )
    return out


def extract_pdf_image_data(document, page, item):
    xref, _, _, _, _, _, _, name, _ = item
    return {
        'rectangle': page.get_image_bbox(name),
        'image': Image.open(io.BytesIO(document.extract_image(xref)['image']))
    }


def extract_xml_invoice_metadata(xml):
    """
    rsm:CrossIndustryInvoice
      rsm:SupplyChainTradeTransaction
        ram:ApplicableHeaderTradeAgreement
          ram:BuyerReference -> Buyer Reference (REF000BSP)
        ram:ApplicableHeaderTradeSettlement
          ram:PaymentReference -> Invoice Number (RE000002)
          ram:SpecifiedTradeSettlementHeaderMonetarySummation
            ram:GrandTotalAmount -> Invoice Amount (40.00€)
    """
    data = xmltodict.parse(xml)
    invoice = data['rsm:CrossIndustryInvoice']
    transaction = invoice['rsm:SupplyChainTradeTransaction']
    agreement = transaction['ram:ApplicableHeaderTradeAgreement']
    settlement = transaction['ram:ApplicableHeaderTradeSettlement']
    summation = settlement['ram:SpecifiedTradeSettlementHeaderMonetarySummation']
    return {
        'buyer_reference': agreement['ram:BuyerReference'],
        'invoice_number': settlement['ram:PaymentReference'],
        'invoice_amount': summation['ram:GrandTotalAmount'],
        'currency': summation['ram:TaxTotalAmount']['@currencyID']
    }


def insert_girocode(
    input_pdf,
    input_xml,
    output_pdf_dest
):
    with open(input_xml, 'r') as file:
        metadata = extract_xml_invoice_metadata(xml=file.read())

    document = fitz.Document(input_pdf)
    page = document.load_page(ENV('GIROCODE_PDF_PAGE_INDEX', to=int))

    images = page.get_images()
    image_index = ENV('GIROCODE_PDF_PAGE_PLACEHOLDER_IMAGE_INDEX', to=int)
    placeholder_image = extract_pdf_image_data(document, page, images[image_index])

    girocode_bytes = create_girocode(
        reference=metadata['buyer_reference'],
        amount=metadata['invoice_amount']
    )
    page.insert_image(placeholder_image['rectangle'], stream=girocode_bytes)
    document.save(output_pdf_dest)
