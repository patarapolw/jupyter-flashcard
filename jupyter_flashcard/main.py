from datetime import datetime, timedelta
import random

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from . import db
from .config import config


class JupyterFlashcard:
    def __init__(self, **kwargs):
        """Supported kwargs are the same as in config dict
        {
            'engine': 'postgresql://localhost/jupyter-flashcard',
            'host': 'localhost',
            'port': 7000,
            'debug': False,
            'threaded': False,
            'srs': {
                1: timedelta(minutes=10),
                2: timedelta(hours=4),
                3: timedelta(hours=8),
                4: timedelta(days=1),
                5: timedelta(days=3),
                6: timedelta(days=7),
                7: timedelta(weeks=2),
                8: timedelta(weeks=4),
                9: timedelta(weeks=16)
            }
        }
        """

        config.update(kwargs)

        self.engine = create_engine(config['engine'])
        self.session = sessionmaker(bind=self.engine)()

        config['session'] = self.session

    def __iter__(self):
        """Default iterator is the same as iterating through files
        
        Returns:
            iterator -- self.files iterator
        """

        return iter(self.files)

    @property
    def files(self):
        """Query object of files
        
        Returns:
            SQLAlchemy Query object -- All db.File's
        """

        return self.session.query(db.File)

    @property
    def flashcards(self):
        """Query object of flashcards
        
        Returns:
            SQLAlchemy Query object -- All db.Flashcard's
        """

        return self.session.query(db.Flashcard)

    @property
    def cells(self):
        """Query object of cells
        
        Returns:
            SQLAlchemy Query object -- All db.Cell's
        """

        return self.session.query(db.Cell)

    def init(self, initial_file_path=None):
        """Initiate the JupyterFlashcard database for the first time
        
        Keyword Arguments:
            initial_file_path {str, pathlib.Path} -- 
                The initial file path to scan for Jupyter Notebook files.
                If None, no initial file path is scanned. 
                (default: {None})
        """

        db.Base.metadata.create_all(self.engine)

        if initial_file_path:
            self.add(initial_file_path)

    def search_files(self, filename=None, tags=None):
        """Searching through files in the database
        
        Keyword Arguments:
            filename {str} -- Substring of filenames (default: {None})
            tags {iterable} -- Iterable of substrings of tags (default: {None})
        Yields:
            db.File SQLAlchemy object -- The object matching the criteria
        """

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
        """Searching through flashcards in the database
        
        Keyword Arguments:
            content {str} -- Substring matching db.Flashcard.data (default: {None})
            min_srs {int} -- Minimal db.Flashcard.srs_level (default: {0})
            max_srs {int} -- Maximal db.Flashcard.srs_level (default: {None})
            due {datetime.datetime, datetime.timedelta} -- 
                Minimal due datetime, or timedelta distance from due datetime
                For example, datetime.now() or timedelta(hours=0)
                (default: {None})
            tags {iterable} -- Iterable of substrings of tags (default: {None})
            filename {str} -- Substring of filename (default: {None})
        Yields:
            db.Flashcard SQLAlchemy object -- The object matching the criteria
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
        """Searching through cells in the database
        
        Keyword Arguments:
            content {str} -- Substring matching db.Cell.data (default: {None})
            filename {str} -- Substring of filename (default: {None})
            tags {iterable} -- Iterable of substring of tags (default: {None})
        
        Yields:
            db.Cell SQLAlchemy object -- The object matching the criteria
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
        """Generate an iterator of db.Flashcard quiz
        
        Keyword Arguments:
            tags {iterable} -- Iterable of substring of tags (default: {None})
        
        Returns:
            iterator -- 
                Iterator of db.Flashcard
                To use it, create a iterator, and then call next() repeatedly (see README.md)
        """

        quiz_list = list(self.search_flashcards(due=datetime.now(), tags=tags))
        random.shuffle(quiz_list)

        return iter(quiz_list)

    def quiz(self, *args, **kwargs):
        """Quiz one db.Flashcard of the quiz
        
        Returns:
            db.Flashcard SQLAlchemy object -- A randomized db.Flashcard matching the criteria
        """

        return next(self.iter_quiz(*args, **kwargs))

    @classmethod
    def add(cls, fp):
        """Add a Jupyter Notebook file to the database
        
        Arguments:
            fp {str|Path} -- A Jupyter Notebook file or a folder containing Jupyter Notebook files.
        """

        db.File.add(fp)

    def update(self, *args, **kwargs):
        """Update all files in the database

        Arguments:
            Same as self.search_files()
        """

        if args or kwargs:
            files = self.search_files(*args, **kwargs)
        else:
            files = self.files

        for db_file in files:
            db_file.update()
