from extraction_service.chunking import Page, split_into_pages, split_into_paragraphs


def test_split_into_pages_uses_form_feed() -> None:
    text = "Page one content.\fPage two content."
    pages = split_into_pages(text, max_chars=10)
    assert len(pages) == 2
    assert pages[0].page_number == 1
    assert pages[1].page_number == 2
    assert "Page one" in pages[0].text


def test_split_into_pages_groups_paragraphs() -> None:
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
    pages = split_into_pages(text, max_chars=20)
    assert len(pages) >= 2
    assert all(page.text for page in pages)


def test_split_into_paragraphs_preserves_indices() -> None:
    page = Page(text="A\n\nB\n\nC", page_number=3)
    paragraphs = split_into_paragraphs(page)
    assert [p.paragraph_index for p in paragraphs] == [0, 1, 2]
    assert all(p.page_number == 3 for p in paragraphs)
