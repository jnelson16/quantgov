"""
quantgov.corpora.builtins: Functions for analyzing a single Document
"""
import re
import collections
import math
import numpy as np
import pandas as pd

from decorator import decorator
import quantgov

try:
    import nltk.corpus
    NLTK = True
except ImportError:
    NLTK = None

try:
    import textblob
except ImportError:
    textblob = None

if NLTK:
    try:
        nltk.corpus.wordnet.ensure_loaded()
    except LookupError:
        nltk.download('wordnet')
        nltk.corpus.wordnet.ensure_loaded()

commands = {}


@decorator
def check_nltk(func, *args, **kwargs):
    if NLTK is None:
        raise RuntimeError('Must install NLTK to use {}'.format(func))
    return func(*args, **kwargs)


@decorator
def check_textblob(func, *args, **kwargs):
    if textblob is None:
        raise RuntimeError('Must install textblob to use {}'.format(func))
    return func(*args, **kwargs)


class WordCounter():

    cli = quantgov.utils.CLISpec(
        help='Word Counter',
        arguments=[
            quantgov.utils.CLIArg(
                flags=('--word_pattern', '-wp'),
                kwargs={
                    'help': 'regular expression defining a "word"',
                    'type': re.compile,
                    'default': re.compile(r'\b\w+\b')
                }
            )
        ]
    )

    @staticmethod
    def get_columns(args):
        return ('words',)

    @staticmethod
    def process_document(doc, word_pattern):
        return doc.index + (len(word_pattern.findall(doc.text)),)


commands['count_words'] = WordCounter


class OccurrenceCounter():

    cli = quantgov.utils.CLISpec(
        help="Term Counter for Specific Words",
        arguments=[
            quantgov.utils.CLIArg(
                flags=('terms'),
                kwargs={
                    'help': 'list of terms to be counted',
                    'nargs': '+'
                }
            ),
            quantgov.utils.CLIArg(
                flags=('--total_label'),
                kwargs={
                    'metavar': 'LABEL',
                    'help': (
                        'output a column with sum of occurrences of all terms'
                        ' with column name LABEL'
                    ),
                }
            ),
            quantgov.utils.CLIArg(
                flags=('--pattern'),
                kwargs={
                    'help': 'pattern to use in identifying words',
                    'default': r'\b(?P<match>{})\b'
                }
            )
        ]
    )

    @staticmethod
    def get_columns(args):
        if args['total_label'] is not None:
            return tuple(args['terms']) + (args['total_label'],)
        return tuple(args['terms'])

    @staticmethod
    def process_document(doc, terms, pattern, total_label):
        text = ' '.join(doc.text.split()).lower()
        terms_sorted = sorted(terms, key=len, reverse=True)
        combined_pattern = re.compile(pattern.format('|'.join(terms_sorted)))
        term_counts = collections.Counter(
            i.groupdict()['match'] for i in combined_pattern.finditer(text)
        )
        if total_label is not None:
            return (
                doc.index
                + tuple(term_counts[i] for i in terms)
                + (sum(term_counts.values()),)
            )
        return (doc.index + tuple(term_counts[i] for i in terms))


commands['count_occurrences'] = OccurrenceCounter


class ShannonEntropy():
    lemmas = {}
    cli = quantgov.utils.CLISpec(
        help='Shannon Entropy',
        arguments=[
            quantgov.utils.CLIArg(
                flags=('--word_pattern', '-wp'),
                kwargs={
                    'help': 'regular expression defining a "word"',
                    'type': re.compile,
                    'default': re.compile(r'\b\w+\b')
                }
            ),
            quantgov.utils.CLIArg(
                flags=('--stopwords', '-sw'),
                kwargs={
                    'help': 'stopwords to ignore',
                    'default': (nltk.corpus.stopwords.words('english')
                                if NLTK else None)
                }
            ),
            quantgov.utils.CLIArg(
                flags=('--precision'),
                kwargs={
                    'help': 'decimal places to round',
                    'default': 2
                }
            )
        ]
    )

    @staticmethod
    def get_columns(args):
        return ('shannon_entropy',)

    @staticmethod
    @check_nltk
    @check_textblob
    def process_document(doc, word_pattern, precision, stopwords,
                         textblob=textblob, nltk=NLTK):
        words = word_pattern.findall(doc.text)
        lemmas = [
            lemma for lemma in (
                ShannonEntropy.lemmatize(word) for word in words
            )
            if lemma not in stopwords
        ]
        counts = collections.Counter(lemmas)
        return doc.index + (round(sum(
            -(count / len(lemmas) * math.log(count / len(lemmas), 2))
            for count in counts.values()
        ), int(precision)),)

    def lemmatize(word):
        if word in ShannonEntropy.lemmas:
            lemma = ShannonEntropy.lemmas[word]
        else:
            lemma = textblob.Word(word).lemmatize()
            ShannonEntropy.lemmas[word] = lemma
        return lemma


commands['shannon_entropy'] = ShannonEntropy


class ConditionalCounter():
    cli = quantgov.utils.CLISpec(
        help=('Count conditional words and phrases. Included terms are: '
              ' "if", "but", "except", "provided", "when", "where", '
              '"whenever", "unless", "notwithstanding", "in the event", '
              'and "in no event"'),
        arguments=[]
    )
    pattern = re.compile(
        r'\b(if|but|except|provided|when|where'
        r'|whenever|unless|notwithstanding'
        r'|in\s+the\s+event|in\s+no\s+event)\b'
    )

    @staticmethod
    def get_columns(args):
        return ('conditionals',)

    @staticmethod
    def process_document(doc):
        return doc.index + (len(ConditionalCounter.pattern.findall(
                                ' '.join((doc.text).splitlines()))),)


commands['count_conditionals'] = ConditionalCounter


class SentenceLength():

    cli = quantgov.utils.CLISpec(
        help='Sentence Length',
        arguments=[
            quantgov.utils.CLIArg(
                flags=('--precision'),
                kwargs={
                    'help': 'decimal places to round',
                    'default': 2
                }
            )
        ]
    )

    @staticmethod
    def get_columns(args):
        return ('sentence_length',)

    @staticmethod
    @check_nltk
    @check_textblob
    def process_document(doc, precision):
        sentences = textblob.TextBlob(doc.text).sentences
        # Allows for rounding to a specified number of decimals
        if precision:
            return doc.index + (round(sum(len(
                sentence.words) for sentence in sentences) /
                len(sentences), int(precision)),)
        else:
            return doc.index + (sum(len(
                sentence.words) for sentence in sentences) /
                len(sentences),)


commands['sentence_length'] = SentenceLength


class SentimentAnalysis():

    cli = quantgov.utils.CLISpec(
        help='Performs sentiment analysis on the text',
        arguments=[
            quantgov.utils.CLIArg(
                flags=('--backend'),
                kwargs={
                    'help': 'which program to use for the analysis',
                    'default': 'textblob'
                }
            ),
            quantgov.utils.CLIArg(
                flags=('--precision'),
                kwargs={
                    'help': 'decimal places to round',
                    'default': 2
                }
            )
        ]
    )

    @staticmethod
    def get_columns(args):
        if args['backend'] == 'textblob':
            return ('sentiment_polarity', 'sentiment_subjectivity',)
        else:
            raise NotImplementedError

    @staticmethod
    @check_nltk
    @check_textblob
    def process_document(doc, backend, precision):
        if backend == 'textblob':
            sentiment = textblob.TextBlob(doc.text)
            # Allows for rounding to a specified number of decimals
            if precision:
                return (doc.index +
                        (round(sentiment.polarity, int(precision)),
                            round(sentiment.subjectivity, int(precision)),))
            else:
                return (doc.index +
                        (sentiment.polarity, sentiment.subjectivity,))


commands['sentiment_analysis'] = SentimentAnalysis


class SanityCheck():

    cli = quantgov.utils.CLISpec(
        help='Performs basic sanity check on corpus metadata',
        arguments=[
            quantgov.utils.CLIArg(
                flags=('--metadata'),
                kwargs={
                    'help': 'which file to use as the metadata',
                    'default': 'data/metadata.csv'
                }
            ),
            quantgov.utils.CLIArg(
                flags=('--cutoff'),
                kwargs={
                    'help': ('proportion of minimum word documents required '
                             'to raise warning'),
                    'default': 0.01
                }
            )
        ]
    )

    @staticmethod
    def create_basic_statistics(args):
        df = pd.read_csv(args['metadata'])
        no_documents = len(df)
        total_words = df.words.sum()
        return no_documents, total_words

    @staticmethod
    def find_extreme_documents(args):
        df = pd.read_csv(args['metadata'])
        # The following code finds the max_words, min_words,
        # and the locations of those documents.
        max_words_doc = df[df.words == np.max(df.words)]\
            .iloc[:, 0:SanityCheck.find_last_idx(df)].values.tolist()[0]
        max_words_doc = '/'.join(str(i) for i in max_words_doc) + '.txt'
        max_words = np.max(df.words)

        min_words_doc = df[df.words == np.min(df.words)]\
            .iloc[:, 0:SanityCheck.find_last_idx(df)].values.tolist()[0]
        min_words_doc = '/'.join(str(i) for i in min_words_doc) + '.txt'
        min_words = np.min(df.words)
        min_words_count = len(df[df.words == np.min(df.words)])

        return (max_words_doc, max_words,
                min_words_doc, min_words, min_words_count)

    @staticmethod
    def raise_warning(args):
        df = pd.read_csv(args['metadata'])
        min_words_count = len(df[df.words == np.min(df.words)])
        return (min_words_count > (len(df) * float(args['cutoff'])))

    def find_last_idx(df):
        for count, column in enumerate(df.columns):
            if column == 'words':
                return count


commands['check_sanity'] = SanityCheck
