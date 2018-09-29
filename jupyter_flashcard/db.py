from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import logging

import IPython.display

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .config import config
from .util import complete_path_split, get_files, read_jupyter
from .enum import FlashcardCellType, CellType

Base = declarative_base()


class Flashcard(Base):
    __tablename__ = 'flashcard'

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    modified = sa.Column(sa.DateTime, server_default=sa.func.now(), server_onupdate=sa.func.now())
    flashcard_cell_connects = relationship('FlashcardCellConnect', order_by='FlashcardCellConnect.id',
                                           back_populates='flashcard')

    srs_level = sa.Column(sa.Integer, server_default='0')
    next_review = sa.Column(sa.DateTime, server_default=sa.func.now())
    tags_str = sa.Column(sa.String(100))

    @property
    def fronts(self):
        return list(self._iter_cell(FlashcardCellType.FRONT))

    @property
    def backs(self):
        return list(self._iter_cell(FlashcardCellType.BACK))

    @property
    def extras(self):
        return list(self._iter_cell(FlashcardCellType.EXTRA))

    @property
    def cells(self):
        return list(self._iter_cell())

    @property
    def tags(self):
        tags_set = set(self.my_tags)

        for cell in self.cells:
            tags_set.update(cell.tags)

        return list(tags_set)

    @property
    def my_tags(self):
        tags_set = set()

        if self.tags_str:
            tags_set.update(self.tags_str.strip().split('\n'))

        return list(tags_set)

    @property
    def filenames(self):
        result_set = set()

        for db_cell in self.cells:
            result_set.update(db_cell.filename)

        return list(result_set)

    @classmethod
    def add(cls, front_ids, back_ids, extra_ids=None):
        db_flashcard = cls()
        config['session'].add(db_flashcard)
        config['session'].commit()

        if extra_ids is None:
            extra_ids = list()

        FlashcardCellConnect.add_from_cell_ids(front_ids, FlashcardCellType.FRONT, db_flashcard)
        FlashcardCellConnect.add_from_cell_ids(back_ids, FlashcardCellType.BACK, db_flashcard)
        FlashcardCellConnect.add_from_cell_ids(extra_ids, FlashcardCellType.EXTRA, db_flashcard)

    def add_tags(self, tags=('marked',)):
        if isinstance(tags, str):
            tag = tags
            if tag not in self.tags:
                my_tags = self.my_tags
                my_tags.append(tag)
                self.tags_str = '\n'.join(my_tags)
                config['session'].commit()
        else:
            for tag in tags:
                self.add_tags(tag)

    def remove_tags(self, tags=('marked',), recursive=False):
        if isinstance(tags, str):
            tag = tags
            my_tags = self.my_tags
            if tag in my_tags:
                my_tags.remove(tag)
                self.tags_str = '\n'.join(my_tags)
                config['session'].commit()
            else:
                if recursive:
                    for cell in self.cells:
                        if tag in cell.tags:
                            cell.remove_tags(tag)
        else:
            for tag in tags:
                self.remove_tags(tag)

    mark = add_tags
    unmark = remove_tags

    def to_dict(self):
        return {
            'id': self.id,
            'fronts': self.fronts,
            'backs': self.backs,
            'extra': self.extras,
            'srs_level': self.srs_level,
            'next_review': self.next_review.isoformat(),
            'modified': self.modified.isoformat(),
            'tags': self.tags,
            'filenames': self.filenames
        }

    def __repr__(self):
        return repr(self.to_dict())

    def _iter_cell(self, type_=None):
        for fcc in self.flashcard_cell_connects:
            if type_:
                if fcc.type_ == type_:
                    yield fcc.cell
            else:
                yield fcc.cell

    def _repr_html_(self):
        self.hide()

        return ''

    def show(self):
        for db_cell in self.backs:
            IPython.display.display(db_cell)

    def hide(self):
        for db_cell in self.fronts:
            IPython.display.display(db_cell)

    def right(self):
        if not self.srs_level:
            self.srs_level = 1
        else:
            self.srs_level = self.srs_level + 1

        self.next_review = (datetime.now()
                            + config['srs'].get(int(self.srs_level), timedelta(weeks=4)))

        for slide in self._iter_cell():
            slide.modified = datetime.now()

        config['session'].commit()

    correct = next_srs = right

    def wrong(self, duration=timedelta(minutes=1)):
        if self.srs_level and self.srs_level > 1:
            self.srs_level = self.srs_level - 1

        return self.bury(duration)

    incorrect = previous_srs = wrong

    def bury(self, duration=timedelta(hours=4)):
        self.next_review = datetime.now() + duration

        for slide in self._iter_cell():
            slide.modified = datetime.now()

        config['session'].commit()


class Cell(Base):
    __tablename__ = 'cell'

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    modified = sa.Column(sa.DateTime, server_default=sa.func.now(), server_onupdate=sa.func.now())

    data = sa.Column(sa.String(50000), nullable=False)
    file_id = sa.Column(sa.Integer, sa.ForeignKey('file.id'), nullable=False)
    tags_str = sa.Column(sa.String(100))

    file_ = relationship('File', back_populates='cells')
    flashcard_cell_connects = relationship('FlashcardCellConnect', order_by='FlashcardCellConnect.id',
                                           back_populates='cell')

    @property
    def flashcards(self):
        return [fcc.to_dict() for fcc in self.flashcard_cell_connects]

    @property
    def tags(self):
        tags_set = set(self.my_tags)
        tags_set.update(self.file_.my_tags)

        return list(tags_set)

    @property
    def my_tags(self):
        tags_set = set()

        if self.tags_str:
            tags_set.update(self.tags_str.strip().split('\n'))

        return list(tags_set)

    @property
    def filename(self):
        return self.file_.name

    @classmethod
    def add(cls, data, file_):
        db_cell = cls()
        db_cell.data = data
        db_cell.file_id = file_.id

        config['session'].add(db_cell)
        config['session'].commit()

        return db_cell

    def add_tags(self, tags=('marked',)):
        if isinstance(tags, str):
            tag = tags
            if tag not in self.tags:
                my_tags = self.my_tags
                my_tags.append(tag)
                self.tags_str = '\n'.join(my_tags)
                config['session'].commit()
        else:
            for tag in tags:
                self.add_tags(tag)

    def remove_tags(self, tags=('marked',), recursive=False):
        if isinstance(tags, str):
            tag = tags
            my_tags = self.my_tags
            if tag in my_tags:
                my_tags.remove(tag)
                self.tags_str = '\n'.join(my_tags)
                config['session'].commit()
            else:
                if recursive:
                    if tag in self.file_.tags:
                        self.file_.remove_tags(tag)
        else:
            for tag in tags:
                self.remove_tags(tag)

    mark = add_tags
    unmark = remove_tags

    def to_dict(self):
        return {
            'id': self.id,
            'data': self.data,
            'modified': self.modified.isoformat(),
            'filename': self.filename,
            'tags': self.tags,
            'flashcards': [fcc.flashcard.id for fcc in self.flashcard_cell_connects]
        }

    def __repr__(self):
        return repr(self.to_dict())

    def _repr_markdown_(self):
        return self.data


class File(Base):
    __tablename__ = 'file'

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String(100), nullable=False)
    checksum = sa.Column(sa.String, nullable=False)
    updated = sa.Column(sa.DateTime, server_default=sa.func.now(), server_onupdate=sa.func.now())
    tags_str = sa.Column(sa.String(100))

    cells = relationship('Cell', back_populates='file_')

    @property
    def path(self):
        return Path(self.name).resolve()

    @property
    def tags(self):
        tags_set = set(self.my_tags)

        for cell in self.cells:
            tags_set.update(cell.tags)

        return list(tags_set)

    @property
    def my_tags(self):
        tags_set = set()

        if self.tags_str:
            tags_set.update(self.tags_str.strip().split('\n'))

        return list(tags_set)

    def add_tags(self, tags=('marked',)):
        if isinstance(tags, str):
            tag = tags
            if tag not in self.tags:
                my_tags = self.my_tags
                my_tags.append(tag)
                self.tags_str = '\n'.join(my_tags)
                config['session'].commit()
        else:
            for tag in tags:
                self.add_tags(tag)

    def remove_tags(self, tags=('marked',), recursive=False):
        if isinstance(tags, str):
            tag = tags
            my_tags = self.my_tags
            if tag in my_tags:
                my_tags.remove(tag)
                self.tags_str = '\n'.join(my_tags)
                config['session'].commit()
            else:
                if recursive:
                    for cell in self.cells:
                        if tag in cell.tags:
                            cell.remove_tags(tag)
        else:
            for tag in tags:
                self.remove_tags(tag)

    mark = add_tags
    unmark = remove_tags

    def to_dict(self):
        return {
            'id': self.id,
            'path': self.path,
            'updated': self.updated.isoformat(),
            'cells': [cell.id for cell in self.cells],
            'tags': self.tags
        }

    def __repr__(self):
        return repr(self.to_dict())

    @classmethod
    def add(cls, file_path):
        file_path = Path(file_path).resolve()

        if file_path.is_dir():
            for fp in get_files(suffixes=['.ipynb'], src=file_path):
                cls.add(fp)
        else:
            file_id = file_path.stat().st_ino
            db_file = config['session'].query(cls).filter_by(id=file_id).first()
            if db_file is None:
                db_file = cls()
                db_file.id = file_id
                db_file.name = str(file_path.resolve())
                db_file.checksum = hashlib.md5(file_path.read_bytes()).hexdigest()
                db_file.tags_str = '\n'.join(complete_path_split(file_path.parent))

                config['session'].add(db_file)
                config['session'].commit()

                db_file.update(forced=True)
            else:
                logging.error('%s already exists.', file_path)

    def _repr_html_(self):
        for db_cell in self.cells:
            IPython.display.display(db_cell)

        return ''

    def is_updated(self):
        if self.path.exists() and self.path.stat().st_ino == self.id:
            if self.checksum != hashlib.md5(self.path.read_bytes()).hexdigest():
                return False
            else:
                return True
        else:
            return None

    def update(self, forced=False):
        if not forced:
            update_status = self.is_updated()
        else:
            update_status = False

        if update_status is None:
            config['session'].delete(self)
            config['session'].commit()
        elif update_status is False:
            fc = dict()
            for cell_data in read_jupyter(self.path):
                do_add = True

                for db_cell in config['session'].query(Cell).filter_by(file_id=self.id):
                    if cell_data != db_cell.data:
                        if db_cell.data in cell_data:
                            do_add = False

                            db_cell.data = cell_data
                            config['session'].commit()
                    else:
                        do_add = False

                if do_add:
                    db_cell = config['session'].query(Cell).filter_by(data=cell_data).first()
                    if db_cell:
                        logging.error('Cannot import cell %s from file %s due to duplicate with %s',
                                      cell_data, self.path, db_cell.filename)
                        return
                    else:
                        db_cell = Cell.add(data=cell_data, file_=self)

                        if cell_data[0] == '#':
                            if len(fc) >= 2:
                                Flashcard.add(**fc)
                                fc = dict()

                            fc.setdefault('front_ids', []).append(db_cell.id)
                        elif 'front_ids' in fc.keys():
                            fc.setdefault('back_ids', []).append(db_cell.id)

        else:
            logging.info('%s is already updated', self.path)


class FlashcardCellConnect(Base):
    __tablename__ = 'flashcard_cell_connect'

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    flashcard_id = sa.Column(sa.Integer, sa.ForeignKey('flashcard.id'), nullable=False)
    cell_id = sa.Column(sa.Integer, sa.ForeignKey('cell.id'), nullable=False)
    type_ = sa.Column(sa.String(10), nullable=False)

    flashcard = relationship('Flashcard', back_populates='flashcard_cell_connects')
    cell = relationship('Cell', back_populates='flashcard_cell_connects')

    def to_dict(self):
        return {
            'id': self.id,
            'flashcard': self.flashcard,
            'cell': self.cell,
            'type': self.type_
        }

    def __repr__(self):
        return repr(self.to_dict())

    @classmethod
    def add_from_cell_ids(cls, cell_ids, type_, db_flashcard):
        for cell_id in cell_ids:
            db_fcc = cls()
            db_fcc.flashcard_id = db_flashcard.id
            db_fcc.cell_id = cell_id
            db_fcc.type_ = type_

            config['session'].add(db_fcc)
            config['session'].commit()
