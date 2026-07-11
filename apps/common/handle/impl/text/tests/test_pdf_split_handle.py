from io import BytesIO
from types import SimpleNamespace

from django.test import SimpleTestCase
from PIL import Image

from common.handle.impl.text.pdf_split_handle import PdfSplitHandle


class FakePage:
    def __init__(self, text="", images=None):
        self.text = text
        self.images = images or []

    def extract_text(self, visitor_text=None):
        if visitor_text is None:
            return self.text
        visitor_text(self.text, [1, 0, 0, 1, 0, 0], [1, 0, 0, 1, 0, 0], None, 12)
        return self.text


class PdfSplitHandleImageTest(SimpleTestCase):
    def test_extract_document_images_creates_oss_references_and_file_models(self):
        image_bytes = b"fake-png-content"
        pdf_document = SimpleNamespace(
            pages=[FakePage(images=[SimpleNamespace(name="page-image.png", data=image_bytes)])]
        )

        page_image_references, image_files = PdfSplitHandle.extract_document_images(pdf_document)

        self.assertEqual(len(image_files), 1)
        self.assertEqual(image_files[0].file_name, "page-image.png")
        self.assertEqual(image_files[0].meta["content"], image_bytes)
        self.assertEqual(
            page_image_references[0],
            [f"![image](./oss/file/{image_files[0].id})"],
        )

    def test_extract_document_images_converts_jpeg2000_to_browser_safe_png(self):
        source_image = Image.new("RGB", (2, 2), color="red")
        pdf_document = SimpleNamespace(
            pages=[
                FakePage(
                    images=[
                        SimpleNamespace(
                            name="unsupported.jp2",
                            data=b"jpeg-2000-content",
                            image=source_image,
                        )
                    ]
                )
            ]
        )

        _, image_files = PdfSplitHandle.extract_document_images(pdf_document)

        self.assertEqual(image_files[0].file_name, "unsupported.png")
        with Image.open(BytesIO(image_files[0].meta["content"])) as converted_image:
            self.assertEqual(converted_image.format, "PNG")
            self.assertEqual(converted_image.size, (2, 2))

    def test_handle_pdf_content_uses_persistable_image_reference_instead_of_placeholder(self):
        pdf_document = SimpleNamespace(pages=[FakePage(text="CDUT")])
        page_image_references = {0: ["![image](./oss/file/019f4c58-6cd6-7792-9b83-0f0e3525dd10)"]}

        content = PdfSplitHandle.handle_pdf_content(
            SimpleNamespace(name="chapter.pdf"),
            pdf_document,
            page_image_references,
        )

        self.assertIn("![image](./oss/file/019f4c58-6cd6-7792-9b83-0f0e3525dd10)", content)
        self.assertNotIn("image_0_0", content)
