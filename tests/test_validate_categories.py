import os
import tempfile
from Mesh.tools import validate_categories as vc


def test_parse_line_ok():
    left, right, cat = vc.parse_line("a video about cats | a photo of cats")
    assert left.startswith("a video about ")
    assert right.startswith("a photo of ")
    assert cat == "cats"


def test_validate_counts_and_dupes(tmp_path: tempfile.TemporaryDirectory):
    p = os.path.join(tmp_path, 'master.txt')
    with open(p, 'w', encoding='utf-8') as f:
        f.write("a video about cats | a photo of cats\n")
        f.write("a video about dogs | a photo of dogs\n")
        f.write("a video about cats | a photo of cats\n")
    rc = vc.validate(p, expect_min=2)
    assert rc in (0, 0)  # function prints warning but returns 0

