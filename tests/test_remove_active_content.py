"""Tests for PdfWriter.remove_active_content()."""

from io import BytesIO

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    IndirectObject,
    NameObject,
    NumberObject,
    TextStringObject,
)


def _action(subtype, extra=None):
    action = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Action"),
            NameObject("/S"): NameObject(subtype),
        }
    )
    if extra:
        action.update(extra)
    return action


def _js_action(code="app.alert('boom');"):
    return _action("/JavaScript", {NameObject("/JS"): TextStringObject(code)})


def _goto_action(page_ref):
    return _action(
        "/GoTo",
        {NameObject("/D"): ArrayObject([page_ref, NameObject("/Fit")])},
    )


def _rect():
    return ArrayObject([NumberObject(0), NumberObject(0), NumberObject(10), NumberObject(10)])


def _link_annot(action_or_dest):
    annot = DictionaryObject(
        {
            NameObject("/Subtype"): NameObject("/Link"),
            NameObject("/Rect"): _rect(),
        }
    )
    annot.update(action_or_dest)
    return annot


def build_hostile_writer():
    """Build a small PDF offline, full of active content entry points."""
    writer = PdfWriter()
    page0 = writer.add_blank_page(width=200, height=200)
    page1 = writer.add_blank_page(width=200, height=200)
    page0_ref = page0.indirect_reference
    page1_ref = page1.indirect_reference
    root = writer.root_object

    # --- Catalog ---
    root[NameObject("/OpenAction")] = writer._add_object(_js_action("app.alert('open');"))
    root[NameObject("/AA")] = DictionaryObject({NameObject("/WC"): _js_action()})
    root[NameObject("/Names")] = DictionaryObject(
        {
            NameObject("/JavaScript"): DictionaryObject(
                {
                    NameObject("/Names"): ArrayObject(
                        [TextStringObject("js1"), writer._add_object(_js_action())]
                    )
                }
            ),
            NameObject("/EmbeddedFiles"): DictionaryObject(
                {
                    NameObject("/Names"): ArrayObject(
                        [
                            TextStringObject("evil.txt"),
                            DictionaryObject({NameObject("/F"): TextStringObject("evil.txt")}),
                        ]
                    )
                }
            ),
            # An unrelated name tree that must survive the cleanup.
            NameObject("/Dests"): DictionaryObject({NameObject("/Names"): ArrayObject()}),
        }
    )
    root[NameObject("/AF")] = ArrayObject(
        [DictionaryObject({NameObject("/F"): TextStringObject("evil.txt")})]
    )

    # --- AcroForm: XFA + additional actions on a field and its kid ---
    kid_field = DictionaryObject(
        {
            NameObject("/T"): TextStringObject("child"),
            NameObject("/AA"): DictionaryObject({NameObject("/F"): _js_action()}),
        }
    )
    field = DictionaryObject(
        {
            NameObject("/FT"): NameObject("/Tx"),
            NameObject("/T"): TextStringObject("parent"),
            NameObject("/V"): TextStringObject("static value"),
            NameObject("/Kids"): ArrayObject([writer._add_object(kid_field)]),
            NameObject("/AA"): DictionaryObject({NameObject("/K"): _js_action()}),
        }
    )
    root[NameObject("/AcroForm")] = DictionaryObject(
        {
            NameObject("/Fields"): ArrayObject([writer._add_object(field)]),
            NameObject("/XFA"): ArrayObject([TextStringObject("preamble")]),
        }
    )

    # --- Outlines: one item with a JavaScript action, one with a destination ---
    outlines = DictionaryObject({NameObject("/Type"): NameObject("/Outlines")})
    outlines_ref = writer._add_object(outlines)
    item_bad = DictionaryObject(
        {
            NameObject("/Title"): TextStringObject("bad item"),
            NameObject("/Parent"): outlines_ref,
            NameObject("/A"): _js_action(),
        }
    )
    item_bad_ref = writer._add_object(item_bad)
    item_good = DictionaryObject(
        {
            NameObject("/Title"): TextStringObject("good item"),
            NameObject("/Parent"): outlines_ref,
            NameObject("/Prev"): item_bad_ref,
            NameObject("/Dest"): ArrayObject([page1_ref, NameObject("/Fit")]),
        }
    )
    item_good_ref = writer._add_object(item_good)
    item_bad[NameObject("/Next")] = item_good_ref
    outlines[NameObject("/First")] = item_bad_ref
    outlines[NameObject("/Last")] = item_good_ref
    outlines[NameObject("/Count")] = NumberObject(2)
    root[NameObject("/Outlines")] = outlines_ref

    # --- Page 0 ---
    page0[NameObject("/AA")] = DictionaryObject({NameObject("/O"): _js_action()})
    page0[NameObject("/AF")] = ArrayObject([DictionaryObject()])

    # A GoTo action whose /Next array mixes good and bad actions.
    goto_mixed = _goto_action(page1_ref)
    goto_mixed[NameObject("/Next")] = ArrayObject(
        [
            _js_action(),
            _goto_action(page0_ref),
            _action("/Launch", {NameObject("/F"): TextStringObject("cmd.exe")}),
        ]
    )
    link_goto_mixed = _link_annot({NameObject("/A"): goto_mixed})

    # A link to an external URI: the annotation stays, the action goes.
    link_uri = _link_annot(
        {
            NameObject("/A"): _action(
                "/URI", {NameObject("/URI"): TextStringObject("https://example.com/")}
            )
        }
    )

    # A link with a plain internal destination: untouched.
    link_dest = _link_annot(
        {NameObject("/Dest"): ArrayObject([page1_ref, NameObject("/Fit")])}
    )

    # A cyclic pair of allowed GoTo actions (A.Next = B, B.Next = A).
    goto_a = _goto_action(page0_ref)
    goto_b = _goto_action(page1_ref)
    goto_a_ref = writer._add_object(goto_a)
    goto_b_ref = writer._add_object(goto_b)
    goto_a[NameObject("/Next")] = goto_b_ref
    goto_b[NameObject("/Next")] = goto_a_ref
    link_cycle = _link_annot({NameObject("/A"): goto_a_ref})

    # One indirect JavaScript action shared by two annotations.
    shared_js_ref = writer._add_object(_js_action())
    link_shared_1 = _link_annot({NameObject("/A"): shared_js_ref})
    link_shared_2 = _link_annot({NameObject("/A"): shared_js_ref})

    # A plain text annotation with additional actions.
    text_annot = DictionaryObject(
        {
            NameObject("/Subtype"): NameObject("/Text"),
            NameObject("/Rect"): _rect(),
            NameObject("/Contents"): TextStringObject("a harmless note"),
            NameObject("/AA"): DictionaryObject({NameObject("/PC"): _js_action()}),
        }
    )

    # Active media annotations: removed entirely.
    media_annots = [
        DictionaryObject({NameObject("/Subtype"): NameObject(subtype), NameObject("/Rect"): _rect()})
        for subtype in ("/RichMedia", "/Movie", "/Sound", "/Screen")
    ]

    page0[NameObject("/Annots")] = ArrayObject(
        [
            link_goto_mixed,
            link_uri,
            link_dest,
            link_cycle,
            link_shared_1,
            link_shared_2,
            text_annot,
            *media_annots,
        ]
    )

    # --- Page 1: an allowed GoTo action with a single bad action chained behind it ---
    goto_bad_next = _goto_action(page0_ref)
    goto_bad_next[NameObject("/Next")] = _js_action()
    page1[NameObject("/AA")] = DictionaryObject({NameObject("/O"): goto_bad_next})

    writer.add_metadata({"/Title": "Passive document", "/Author": "tester"})
    return writer


def _walk_objects(root):
    """Yield every dictionary reachable from the given object."""
    seen = set()

    def walk(obj):
        if isinstance(obj, IndirectObject):
            key = (obj.idnum, obj.generation)
            if key in seen:
                return
            seen.add(key)
            obj = obj.get_object()
        if isinstance(obj, DictionaryObject):
            yield obj
            for value in obj.values():
                yield from walk(value)
        elif isinstance(obj, ArrayObject):
            for value in obj:
                yield from walk(value)

    yield from walk(root)


def test_remove_active_content__roundtrip_object_graph_is_clean():
    writer = build_hostile_writer()
    writer.remove_active_content()
    buffer = BytesIO()
    writer.write(buffer)

    reader = PdfReader(BytesIO(buffer.getvalue()))
    root = reader.root_object

    # Catalog
    assert "/OpenAction" not in root
    assert "/AA" not in root
    assert "/AF" not in root
    names = root["/Names"]
    assert "/JavaScript" not in names
    assert "/EmbeddedFiles" not in names
    assert "/Dests" in names  # unrelated name trees are kept

    # AcroForm: XFA gone, static fields kept
    acro_form = root["/AcroForm"]
    assert "/XFA" not in acro_form
    field = acro_form["/Fields"][0].get_object()
    assert field["/T"] == "parent"
    assert field["/V"] == "static value"
    assert "/AA" not in field
    kid = field["/Kids"][0].get_object()
    assert kid["/T"] == "child"
    assert "/AA" not in kid

    # Pages
    assert len(reader.pages) == 2
    page0, page1 = reader.pages
    assert "/AA" not in page0
    assert "/AF" not in page0

    # Page 1: the allowed GoTo survived, its bad /Next tail was dropped
    open_action = page1["/AA"]["/O"]
    assert open_action["/S"] == "/GoTo"
    assert "/Next" not in open_action

    # Annotations: media gone, the rest kept
    annots = [a.get_object() for a in page0["/Annots"]]
    subtypes = [a["/Subtype"] for a in annots]
    assert subtypes == ["/Link"] * 6 + ["/Text"]

    link_goto_mixed, link_uri, link_dest, link_cycle, link_shared_1, link_shared_2 = (
        annots[:6]
    )

    # Mixed /Next array: only the internal GoTo action was kept
    action = link_goto_mixed["/A"]
    assert action["/S"] == "/GoTo"
    next_actions = action["/Next"]
    assert isinstance(next_actions, ArrayObject)
    assert len(next_actions) == 1
    assert next_actions[0]["/S"] == "/GoTo"

    # URI action removed, link annotation kept
    assert "/A" not in link_uri

    # Plain destination link untouched
    assert list(link_dest["/Dest"]) == list(
        ArrayObject([page1.indirect_reference, NameObject("/Fit")])
    )

    # Cyclic GoTo chain: kept, and reading it does not hang
    assert link_cycle["/A"]["/S"] == "/GoTo"
    assert link_cycle["/A"]["/Next"]["/S"] == "/GoTo"

    # Shared indirect JavaScript action removed from both annotations
    assert "/A" not in link_shared_1
    assert "/A" not in link_shared_2

    # Text annotation kept, additional actions removed
    text_annot = annots[6]
    assert text_annot["/Contents"] == "a harmless note"
    assert "/AA" not in text_annot

    # Outlines: JavaScript action gone, destination intact
    outlines = root["/Outlines"]
    first = outlines["/First"].get_object()
    assert first["/Title"] == "bad item"
    assert "/A" not in first
    second = first["/Next"].get_object()
    assert second["/Title"] == "good item"
    assert "/Dest" in second

    # Metadata preserved
    assert reader.metadata.title == "Passive document"
    assert reader.metadata.author == "tester"

    # Global invariant: no reachable action entry points remain
    for dictionary in _walk_objects(reader.trailer["/Root"]):
        assert "/JS" not in dictionary
        assert "/XFA" not in dictionary
        assert "/AF" not in dictionary
        if dictionary.get("/Type") == "/Action":
            assert dictionary["/S"] == "/GoTo"
        assert dictionary.get("/Subtype") not in (
            "/RichMedia",
            "/Movie",
            "/Sound",
            "/Screen",
        )


def test_remove_active_content__idempotent():
    writer = build_hostile_writer()
    writer.remove_active_content()
    buffer1 = BytesIO()
    writer.write(buffer1)

    writer.remove_active_content()
    buffer2 = BytesIO()
    writer.write(buffer2)

    assert buffer1.getvalue() == buffer2.getvalue()


def test_remove_active_content__does_not_modify_source_reader():
    writer = build_hostile_writer()
    buffer = BytesIO()
    writer.write(buffer)
    data = buffer.getvalue()

    reader = PdfReader(BytesIO(data))
    cloned = PdfWriter()
    cloned.clone_document_from_reader(reader)
    cloned.remove_active_content()
    cleaned_buffer = BytesIO()
    cloned.write(cleaned_buffer)

    # The source reader is untouched
    assert "/OpenAction" in reader.root_object
    assert "/JavaScript" in reader.root_object["/Names"]
    assert "/AA" in reader.pages[0]

    # The cleaned copy is clean
    cleaned = PdfReader(BytesIO(cleaned_buffer.getvalue()))
    assert "/OpenAction" not in cleaned.root_object
    for dictionary in _walk_objects(cleaned.trailer["/Root"]):
        assert "/JS" not in dictionary
        if dictionary.get("/Type") == "/Action":
            assert dictionary["/S"] == "/GoTo"


def test_remove_active_content__open_action_destination_array_is_kept():
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    page1 = writer.add_blank_page(width=200, height=200)
    writer.root_object[NameObject("/OpenAction")] = ArrayObject(
        [page1.indirect_reference, NameObject("/Fit")]
    )

    writer.remove_active_content()
    buffer = BytesIO()
    writer.write(buffer)

    reader = PdfReader(BytesIO(buffer.getvalue()))
    open_action = reader.root_object["/OpenAction"]
    assert isinstance(open_action, ArrayObject)
    assert open_action[0].get_object() == reader.pages[1]
    assert open_action[1] == "/Fit"
    assert len(reader.pages) == 2  # pages remain readable


def test_remove_active_content__open_action_goto_is_kept():
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    page1 = writer.add_blank_page(width=200, height=200)
    goto = _goto_action(page1.indirect_reference)
    goto[NameObject("/Next")] = _js_action()
    writer.root_object[NameObject("/OpenAction")] = goto

    writer.remove_active_content()
    buffer = BytesIO()
    writer.write(buffer)

    reader = PdfReader(BytesIO(buffer.getvalue()))
    open_action = reader.root_object["/OpenAction"]
    assert open_action["/S"] == "/GoTo"
    assert "/Next" not in open_action


def test_remove_active_content__open_action_named_destination_is_kept():
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.root_object[NameObject("/OpenAction")] = TextStringObject("chapter1")

    writer.remove_active_content()
    buffer = BytesIO()
    writer.write(buffer)

    reader = PdfReader(BytesIO(buffer.getvalue()))
    assert reader.root_object["/OpenAction"] == "chapter1"


def test_remove_active_content__empty_writer():
    writer = PdfWriter()
    writer.remove_active_content()  # must not raise
    buffer = BytesIO()
    writer.write(buffer)
    reader = PdfReader(BytesIO(buffer.getvalue()))
    assert len(reader.pages) == 0
