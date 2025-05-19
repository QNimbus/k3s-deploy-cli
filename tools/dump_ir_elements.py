# file: tools/dump_ir_elements.py
# -*- coding: utf-8 -*-

"""
Dumps the initial Intermediate Representation (IR) elements for a specific
PDF page, correlating them back to the raw elements they originated from.

Helps in debugging element structure and content before subsequent plugins run.
"""

import argparse
import logging
from pathlib import Path
import sys
from typing import List, Dict, Tuple

# Ensure the script can find the pdf2md package
# Assumes the script is run from the project root (pdf2md/)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from pdf2md.adapters.pdfplumber_adapter import PdfPlumberAdapter
    from pdf2md.plugins.element_converter import RawElementConverterPlugin
    from pdf2md.ir import DocumentElement, TextBlock, Image, VectorElement, FontStyle
    # Import RawText explicitly for type checking
    from pdf2md.adapters.raw_types import RawElement, RawText, RawImage, RawVectorPath
except ImportError as e:
    print(f"Error importing pdf2md components: {e}")
    print("Please ensure you have run 'pip install -e .' in the project root.")
    sys.exit(1)

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger(__name__)
logging.getLogger('pdf2md.plugins.element_converter').setLevel(logging.INFO) # Keep converter logs concise


def get_raw_elements(pdf_path: Path, page_index_0_based: int) -> List[RawElement]:
    """
    Extracts raw elements for a given page.

    Args:
        pdf_path: Path to the PDF file.
        page_index_0_based: The 0-based page number to process.

    Returns:
        A list of RawElement objects, or an empty list on error.
    """
    raw_elements: List[RawElement] = []
    try:
        logger.info("Instantiating PdfPlumberAdapter...")
        with PdfPlumberAdapter(str(pdf_path)) as adapter:
            if page_index_0_based >= adapter.get_page_count():
                logger.error(
                    f"Page index {page_index_0_based} is out of range "
                    f"(Max: {adapter.get_page_count() - 1})"
                )
                return []
            logger.info(f"Extracting raw elements from page index {page_index_0_based}...")
            raw_elements = adapter.get_page_elements(page_index_0_based)
            logger.info(f"Extracted {len(raw_elements)} raw elements.")
    except Exception as e:
        logger.error(f"Error during PDF extraction: {e}", exc_info=True)
        return []
    return raw_elements


def dump_page_ir_with_raw(pdf_path: Path, page_num_1_based: int) -> None:
    """
    Extracts raw elements, converts to IR, sorts, and prints details including
    the raw source index for correlation.

    Args:
        pdf_path: Path to the PDF file.
        page_num_1_based: The 1-based page number to process.
    """
    if not pdf_path.is_file():
        logger.error(f"PDF file not found: {pdf_path}")
        return

    page_index_0_based = page_num_1_based - 1
    logger.info(f"Processing {pdf_path.name}, Page {page_num_1_based} (Index {page_index_0_based})")

    # 1. Extract Raw Elements
    raw_elements = get_raw_elements(pdf_path, page_index_0_based)
    if not raw_elements:
        logger.warning("No raw elements extracted.")
        return
    # Create a dictionary for easy lookup by original index
    raw_elements_dict: Dict[int, RawElement] = {i: el for i, el in enumerate(raw_elements)}

    # 2. Convert Raw Elements to Initial IR
    converter_plugin = RawElementConverterPlugin()
    logger.info("Running RawElementConverterPlugin...")
    initial_ir_elements: List[DocumentElement] = []
    try:
        # The converter plugin *should* add 'source_index' to metadata
        initial_ir_elements = converter_plugin.process(raw_elements)
        logger.info(f"Converter produced {len(initial_ir_elements)} initial IR elements.")
    except Exception as e:
        logger.error(f"Error running RawElementConverterPlugin: {e}", exc_info=True)
        return

    if not initial_ir_elements:
        logger.warning("No initial IR elements created.")
        return

    # 3. Sort IR Elements by Vertical Position (y0) then Horizontal (x0)
    initial_ir_elements.sort(key=lambda el: (el.bbox[1], el.bbox[0]))

    # 4. Dump Details with Raw Correlation
    print("\n--- Sorted Initial IR Elements (with Raw Source Info) ---")
    print(f"Page: {page_num_1_based}")
    print("----------------------------------------------------------")
    for i, ir_elem in enumerate(initial_ir_elements):
        # Print IR Element Details
        bbox_str = f"({ir_elem.bbox[0]:.1f}, {ir_elem.bbox[1]:.1f}, {ir_elem.bbox[2]:.1f}, {ir_elem.bbox[3]:.1f})"
        print(f"[{i:03d}] Type={type(ir_elem).__name__:<14} BBox={bbox_str}", end="")

        if isinstance(ir_elem, TextBlock):
            # Use repr() to show potential hidden/special characters clearly
            print(f" Style={ir_elem.style} Text={repr(ir_elem.text)}")
        elif isinstance(ir_elem, Image):
            print(f" Src='{ir_elem.src}' Alt='{ir_elem.alt}'")
        elif isinstance(ir_elem, VectorElement):
            print(f" PathType='{ir_elem.path_type}'")
        else:
            print() # Just newline for other types

        # Print Correlated Raw Element Details
        raw_idx = ir_elem.metadata.get('source_index') # Use get() for safety
        if raw_idx is not None:
            raw_elem = raw_elements_dict.get(raw_idx)
            if raw_elem:
                raw_bbox_str = f"({raw_elem.bbox[0]:.1f}, {raw_elem.bbox[1]:.1f}, {raw_elem.bbox[2]:.1f}, {raw_elem.bbox[3]:.1f})"
                raw_type_str = type(raw_elem).__name__
                print(f"  Raw Src [Idx {raw_idx:03d}]: Type={raw_type_str:<12} BBox={raw_bbox_str}", end="")
                if isinstance(raw_elem, RawText):
                     # Print original raw text using repr()
                     print(f" Text={repr(raw_elem.text)}")
                elif isinstance(raw_elem, RawImage):
                     print(f" Stream='{raw_elem.stream_name}' W={raw_elem.width} H={raw_elem.height}")
                elif isinstance(raw_elem, RawVectorPath):
                     print(f" Type='{raw_elem.path_type}' StrokeW={raw_elem.stroke_width}")
                else:
                     print() # Newline for other raw types
            else:
                 print(f"  Raw Src [Idx {raw_idx:03d}]: Not found in original raw list!")
        else:
            print(f"  Raw Src: Index not found in metadata for IR element {i}")


    print("----------------------------------------------------------")
    logger.info("Dump complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Dump initial IR elements for a specific PDF page, showing raw source."
    )
    parser.add_argument("pdf_file", type=str, help="Path to the PDF file.")
    parser.add_argument(
        "page_number", type=int, help="1-based page number to process."
    )
    args = parser.parse_args()

    pdf_path_arg = Path(args.pdf_file)
    page_number_arg = args.page_number

    dump_page_ir_with_raw(pdf_path_arg, page_number_arg)