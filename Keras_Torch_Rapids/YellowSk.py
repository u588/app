#https://www.scikit-yb.org/zh/latest/tutorial.html#id4
import pandas as pd
dataset   = pd.read_csv(mushrooms)
dataset.columns = names
features = ['cap-shape', 'cap-surface', 'cap-color']
target   = ['class']

X = dataset[features]
y = dataset[target]




from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import LabelEncoder, OneHotEncoder


class EncodeCategorical(BaseEstimator, TransformerMixin):
    """
    Encodes a specified list of columns or all columns if None.
    """
    def __init__(self, columns=None):
        self.columns  = [col for col in columns]
        self.encoders = None
    def fit(self, data, target=None):
        """
        Expects a data frame with named columns to encode.
        """
        # Encode all columns if columns is None
        if self.columns is None:
            self.columns = data.columns
        # Fit a label encoder for each column in the data frame
        self.encoders = {
            column: LabelEncoder().fit(data[column])
            for column in self.columns
        }
        return self
    def transform(self, data):
        """
        Uses the encoders to transform a data frame.
        """
        output = data.copy()
        for column, encoder in self.encoders.items():
            output[column] = encoder.transform(data[column])
        return output
from sklearn.metrics import f1_score
from sklearn.pipeline import Pipeline


def model_selection(X, y, estimator):
    """
    Test various estimators.
    """
    y = LabelEncoder().fit_transform(y.values.ravel())
    model = Pipeline([
         ('label_encoding', EncodeCategorical(X.keys())),
         ('one_hot_encoder', OneHotEncoder()),
         ('estimator', estimator)
    ])
    # Instantiate the classification model and visualizer
    model.fit(X, y)
    expected  = y
    predicted = model.predict(X)
    # Compute and return the F1 score (the harmonic mean of precision and recall)
    return (f1_score(expected, predicted))

# Try them all!
from sklearn.svm import LinearSVC, NuSVC, SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegressionCV, LogisticRegression, SGDClassifier
from sklearn.ensemble import BaggingClassifier, ExtraTreesClassifier, RandomForestClassifier

model_selection(X, y, LinearSVC())
model_selection(X, y, NuSVC())
model_selection(X, y, SVC())
model_selection(X, y, SGDClassifier())
model_selection(X, y, KNeighborsClassifier())
model_selection(X, y, LogisticRegressionCV())
model_selection(X, y, LogisticRegression())
model_selection(X, y, BaggingClassifier())
model_selection(X, y, ExtraTreesClassifier())
model_selection(X, y, RandomForestClassifier())



from sklearn.pipeline import Pipeline
from yellowbrick.classifier import ClassificationReport


def visual_model_selection(X, y, estimator):
    """
    Test various estimators.
    """
    y = LabelEncoder().fit_transform(y.values.ravel())
    model = Pipeline([
         ('label_encoding', EncodeCategorical(X.keys())),
         ('one_hot_encoder', OneHotEncoder()),
         ('estimator', estimator)
    ])
    # Instantiate the classification model and visualizer
    visualizer = ClassificationReport(model, classes=['edible', 'poisonous'])
    visualizer.fit(X, y)
    visualizer.score(X, y)
    visualizer.poof()


visual_model_selection(X, y, LinearSVC())
visual_model_selection(X, y, NuSVC())
visual_model_selection(X, y, SVC())
visual_model_selection(X, y, SGDClassifier())
visual_model_selection(X, y, KNeighborsClassifier())
visual_model_selection(X, y, LogisticRegressionCV())
visual_model_selection(X, y, LogisticRegression())
visual_model_selection(X, y, BaggingClassifier())
visual_model_selection(X, y, ExtraTreesClassifier())
visual_model_selection(X, y, RandomForestClassifier())