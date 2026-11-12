# Removing active content

PDF documents can contain active content: JavaScript that runs when the
document is opened or a page is turned, actions that launch applications,
open URLs, submit forms, or jump to other files, embedded files, XFA forms,
and rich media annotations. When you receive a PDF that you only want to
read, {func}`~pypdf.PdfWriter.remove_active_content` strips those entry
points while keeping the document itself readable.

```python
from pypdf import PdfReader, PdfWriter

writer = PdfWriter(clone_from="received.pdf")
writer.remove_active_content()

with open("passive.pdf", "wb") as fp:
    writer.write(fp)

# The cleaned file can be opened and navigated as usual.
reader = PdfReader("passive.pdf")
print(len(reader.pages))
```

The cleanup walks the objects reachable from the document root and removes
or sanitizes:

* **Catalog**: `/OpenAction` (kept when it is a plain destination, i.e. an
  array, a destination dictionary, or a named destination), `/AA`, the
  `/JavaScript` and `/EmbeddedFiles` name trees in `/Names`, and the `/AF`
  associated-files entry.
* **AcroForm**: the `/XFA` entry, plus additional actions (`/AA`) on form
  fields and their descendants. Static fields are kept.
* **Pages**: `/AA`, `/AF`, and annotations of subtype `/RichMedia`,
  `/Movie`, `/Sound`, or `/Screen` (removed entirely). Other annotations —
  text notes, link rectangles, widgets — are kept, but their `/A` action
  and `/AA` additional actions are sanitized.
* **Outlines**: the `/A` action of outline items is sanitized; `/Dest`
  destinations are left untouched.
* **Actions**: only internal `/GoTo` actions are kept. `/JavaScript`,
  `/Launch`, `/URI`, `/GoToR`, `/SubmitForm`, and all other action types
  are removed. The `/Next` chain of a kept action is sanitized as well,
  whether it is a single action dictionary or an array; in an array, only
  the disallowed entries are dropped, so an allowed `GoTo` followed by a
  disallowed action keeps the `GoTo` and loses the tail.

Properties of the cleanup:

* It is **idempotent**: running it twice has the same effect as running it
  once.
* Objects cloned from a `PdfReader` into the writer are copies, so the
  source reader is never modified.
* Only references are removed: objects that become unreachable are not
  scrubbed from the file, and this method does not claim to protect
  against all PDF viewer vulnerabilities.
