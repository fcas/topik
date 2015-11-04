from abc import ABCMeta, abstractmethod, abstractproperty
from collections import Counter

import pandas as pd
from six import with_metaclass


# doctest-only imports
from topik.fileio import read_input
from topik.tests import test_data_path




class TopicModelResultBase(with_metaclass(ABCMeta)):
    """Abstract base class for topic models.

    Ensures consistent interface across models, for base result display capabilities.

    Attributes
    ----------
    _corpus : topik.fileio.digested_document_collection.DigestedDocumentCollection-derived object
        The input data for this model
    _persistor : topik.fileio.persistor.Persistor object
        The object responsible for persisting the state of this model to disk.  Persistor saves metadata
        that instructs load_model how to load the actual data.
    """
    _corpus = None

    @abstractmethod
    def get_top_words(self, topn):
        top_words = []
        # each "topic" is a row of the dz matrix
        for topic in self.dz.T:
            word_ids = np.argpartition(topic, -topn)[-topn:]
            word_ids = reversed(word_ids[np.argsort(topic[word_ids])])
            top_words.append([(topic[word_id], self._corpus.get_id2word_dict()[word_id]) for word_id in word_ids])
        return top_words
        """Abstract method.  Implementations should collect top n words per topic, translate indices/ids to words.

        Returns
        -------
        list of lists of tuples:
            * outer list: topics
            * inner lists: length topn collection of (weight, word) tuples
        """
        raise NotImplementedError

    @abstractmethod
    def save(self, filename, saved_data):
        """Abstract method.  Persist the model metadata and data to disk.

        Implementations should both save their important data do disk with some known keyword
        (perhaps as filename or server address details), and pass a dictionary to saved_data.
        The contents of this dictionary will be passed to the class' constructor as **kwargs.

        Be sure to either call super(YourClass, self).save(filename, saved_data) or otherwise
        duplicate the base level of functionality here.

        Parameters
        ----------
        filename : str
            The filename of the JSON file to be saved, containing model and corpus metadata
            that allow for reconstruction
        saved_data : dict
            Dictionary of metadata that will be fed to class __init__ method at load time.
            This should include such things as number of topics modeled, binary filenames,
            and any other relevant model parameters to recreate your current model.
        """

        self._persistor.store_model(self.get_model_name_with_parameters(),
                                   {"class": self.__class__.__name__,
                                    "saved_data": saved_data})
        self._corpus.save(filename)

    def term_topic_matrix(self):
        self._corpus.term_topic_matrix

    @abstractmethod
    def get_model_name_with_parameters(self):
        """Abstract method.  Primarily internal function, used to name configurations in persisted metadata for later retrieval."""
        raise NotImplementedError

    def _get_term_data(self):
        vocab = self._get_vocab()
        tf = self._get_term_frequency()
        ttd = self._get_topic_term_dists()
        term_data_df = ttd
        term_data_df['term_frequency'] = tf
        term_data_df['term'] = vocab
        return term_data_df

    def _get_vocab(self):
        return pd.Series(dict(self._corpus._dict.items()))

    def _get_term_frequency(self):
        tf = Counter()
        [tf.update(dict(doc)) for doc in self._corpus]
        # TODO update term documents in intermediate store
        return pd.Series(dict(tf))

    def _get_doc_data(self):
        doc_data_df = self._get_doc_topic_dists()
        doc_data_df['doc_length'] = self._get_doc_lengths()
        return doc_data_df

    def _get_doc_lengths(self):
        id_index, doc_lengths = zip(*[(id, len(doc)) for id, doc in list(
                                                        self._corpus._corpus)])
        return pd.Series(doc_lengths, index=id_index)

    @abstractproperty
    def doc_topic_dists(self):
        raise NotImplementedError

    def to_py_lda_vis(self):
        doc_data_df = self._get_doc_data()
        term_data_df = self._get_term_data()

        model_lda_vis_data = {  'vocab': term_data_df['term'],
                                'term_frequency': term_data_df['term_frequency'],
                                'topic_term_dists': term_data_df.iloc[:,:-2].T,
                                'doc_topic_dists': doc_data_df.iloc[:,:-1],
                                'doc_lengths': doc_data_df['doc_length']}
        return model_lda_vis_data

    def termite_data(self, topn_words=15):
        """Generate the pandas dataframe input for the termite plot.

        Parameters
        ----------
        topn_words : int
            number of words to include from each topic

        Examples
        --------


        >> import random
        >> import numpy
        >> import os
        >> import topik.models
        >> random.seed(42)
        >> numpy.random.seed(42)
        >> model = load_model(os.path.join(os.path.dirname(os.path.realpath("__file__")),
        >> model = load_model('{}/doctest.model'.format(test_data_path),
        ...                    model_name="LDA_3_topics")
        >> model.termite_data(5)
            topic    weight           word
        0       0  0.005735             nm
        1       0  0.005396          phase
        2       0  0.005304           high
        3       0  0.005229     properties
        4       0  0.004703      composite
        5       1  0.007056             nm
        6       1  0.006298           size
        7       1  0.005977           high
        8       1  0.005291  nanoparticles
        9       1  0.004737    temperature
        10      2  0.006557           high
        11      2  0.005302      materials
        12      2  0.004439  nanoparticles
        13      2  0.004219           size
        14      2  0.004149              c

        """
        from itertools import chain
        return pd.DataFrame(list(chain.from_iterable([{"topic": topic_id, "weight": weight, "word": word}
                                                      for (weight, word) in topic]
                                                     for topic_id, topic in enumerate(self.get_top_words(topn_words)))))

    @property
    def _persistor(self):
        return self._corpus.persistor


def load_model(filename, model_name):
    """Loads a JSON file containing instructions on how to load model data.

    Returns
    -------
    TopicModelBase-derived object
    """
    from topik.models import registered_models
    p = Persistor(filename)
    if model_name in p.list_available_models():
        data_dict = p.get_model_details(model_name)
        model = registered_models[data_dict['class']](**data_dict["saved_data"])
    else:
        raise NameError("Model name {} has not yet been created.".format(model_name))
    return model
