from datetime import datetime, timedelta
import random

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from . import db
from .config import config


class JupyterFlashcard:
    def __init__(self, **kwargs):
        config.update(kwargs)

        self.engine = create_engine(config['engine'])
        self.session = sessionmaker(bind=self.engine)()

        config['session'] = self.session

    def __iter__(self):
        return iter(self.files)

    @property
    def files(self):
        return self.session.query(db.File)

    @property
    def flashcards(self):
        return self.session.query(db.Flashcard)

    @property
    def cells(self):
        return self.session.query(db.Cell)

    def init(self, initial_file_path=None):
        db.Base.metadata.create_all(self.engine)

        if initial_file_path:
            self.add(initial_file_path)

    def search_files(self, filename=None, tags=None):
        for db_file in self.files:
            if filename:
                if filename not in db_file.name:
                    continue
            if tags:
                do_continue = False
                for tag in tags:
                    if tag not in db_file.tags:
                        do_continue = True
                        break
                if do_continue:
                    continue

            yield db_file

    def search_flashcards(self,
                          content=None,
                          min_srs=0, max_srs=None,
                          due=None,
                          tags=None,
                          filename=None):
        """

        :return:
        keywords to query: {
            'cells': self.cells,
            'srs_level': self.srs_level,
            'next_review': self.next_review,
            'modified': self.modified,
            'tags': self.tags,
            'filenames': self.filenames
        }
        """
        def _has_content(_db_flashcard):
            for _db_cell in _db_flashcard.cells:
                if content in _db_cell.data:
                    return True

            return False

        def _has_tag(_db_flashcard, _tag):
            for t in _db_flashcard.tags:
                if _tag in t:
                    return True

            return False

        def _has_tags(_db_flashcard, _tags):
            for _tag in _tags:
                if _has_tag(_db_flashcard, _tag):
                    return True

            return False

        def _has_filename(_db_flashcard):
            for _filename in _db_flashcard.filenames:
                if filename in _filename:
                    return True

            return False

        if not max_srs:
            max_srs = len(config['srs']) + 1

        for db_flashcard in self.flashcards:
            if content:
                if not _has_content(db_flashcard):
                    continue

            if db_flashcard.srs_level not in range(min_srs, max_srs + 1):
                continue

            if due:
                if isinstance(due, timedelta):
                    due = datetime.now() + due

                if db_flashcard.next_review > due:
                    continue

            if tags:
                if not _has_tags(db_flashcard, tags):
                    continue

            if filename:
                if not _has_filename(db_flashcard):
                    continue

            yield db_flashcard

    def search_cells(self,
                     content=None,
                     filename=None,
                     tags=None):
        """

        :return:
        keywords to query: {
            'data': self.data,
            'filename': self.filename,
            'tags': self.tags
        }
        """

        def _has_tag(_db_cell, _tag):
            for t in _db_cell.tags:
                if _tag in t:
                    return True

            return False

        def _has_tags(_db_cell, _tags):
            for _tag in _tags:
                if _has_tag(_db_cell, _tag):
                    return True

            return False

        for db_cell in self.cells:
            if content:
                if content not in db_cell.data:
                    continue

            if filename:
                if filename not in db_cell.filename:
                    continue

            if tags:
                if not _has_tags(db_cell, tags):
                    continue

            yield db_cell

    def iter_quiz(self, tags=None):
        quiz_list = list(self.search_flashcards(due=datetime.now(), tags=tags))
        random.shuffle(quiz_list)

        return iter(quiz_list)

    def quiz(self, *args, **kwargs):
        return next(self.iter_quiz(*args, **kwargs))

    @classmethod
    def add(cls, fp):
        db.File.add(fp)

    def update(self):
        for db_file in self.files:
            db_file.update()
