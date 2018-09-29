from pathlib import Path
import json
from collections import OrderedDict
import html

from .enum import CellType


def complete_path_split(path, relative_to=None):
    components = []

    path = Path(path)
    if relative_to:
        path = path.relative_to(relative_to)

    while path.name:
        components.append(path.name)

        path = path.parent

    return components


def get_files(suffixes, src):
    suffixes = set(s.lower() for s in suffixes)

    for fp in Path(src).glob('**/*.*'):
        if fp.is_file() and fp.suffix.lower() in suffixes \
                and not any(comp[0] in {'.', '_'} for comp in complete_path_split(fp)):
            yield fp


def read_jupyter(fp):
    with Path(fp).open() as f:
        for cell in json.load(f, object_pairs_hook=OrderedDict).get('cells', []):
            if cell['cell_type'] == 'code':
                for output in cell.get('outputs', []):
                    if output['output_type'] == 'display_data':
                        data = output['data']
                        types = data.keys()
                        if CellType.HTML in types:
                            yield ''.join(data[CellType.HTML])
                        elif CellType.PLAIN in types:
                            yield '<pre></pre>'.format(html.escape(''.join(data[CellType.PLAIN])))
                        else:
                            raise TypeError(repr(types))

            elif cell['cell_type'] == CellType.MARKDOWN:
                yield ''.join(cell['source'])
