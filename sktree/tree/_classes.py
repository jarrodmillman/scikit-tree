import copy
from numbers import Integral, Real

import numpy as np
from scipy.sparse import issparse
from sklearn.base import ClusterMixin, TransformerMixin, is_classifier
from sklearn.cluster import AgglomerativeClustering
from sklearn.tree import BaseDecisionTree, DecisionTreeClassifier, _criterion
from sklearn.tree import _tree as _sklearn_tree
from sklearn.tree._criterion import BaseCriterion
from sklearn.tree._tree import BestFirstTreeBuilder, DepthFirstTreeBuilder
from sklearn.utils._param_validation import Interval
from sklearn.utils.validation import check_is_fitted

from . import (  # type: ignore
    _morf_splitter,
    _oblique_splitter,
    _unsup_criterion,
    _unsup_oblique_splitter,
    _unsup_splitter,
)
from ._morf_splitter import PatchSplitter
from ._oblique_splitter import ObliqueSplitter
from ._oblique_tree import ObliqueTree
from ._unsup_criterion import UnsupervisedCriterion
from ._unsup_oblique_splitter import UnsupervisedObliqueSplitter
from ._unsup_oblique_tree import UnsupervisedObliqueTree
from ._unsup_splitter import UnsupervisedSplitter
from ._unsup_tree import (  # type: ignore
    UnsupervisedBestFirstTreeBuilder,
    UnsupervisedDepthFirstTreeBuilder,
    UnsupervisedTree,
)

DTYPE = _sklearn_tree.DTYPE
DOUBLE = _sklearn_tree.DOUBLE

CRITERIA_CLF = {
    "gini": _criterion.Gini,
    "log_loss": _criterion.Entropy,
    "entropy": _criterion.Entropy,
}
CRITERIA_REG = {
    "squared_error": _criterion.MSE,
    "friedman_mse": _criterion.FriedmanMSE,
    "absolute_error": _criterion.MAE,
    "poisson": _criterion.Poisson,
}


OBLIQUE_DENSE_SPLITTERS = {
    "best": _oblique_splitter.BestObliqueSplitter,
}

PATCH_DENSE_SPLITTERS = {
    "best": _morf_splitter.BestPatchSplitter,
}

UNSUPERVISED_CRITERIA = {"twomeans": _unsup_criterion.TwoMeans, "fastbic": _unsup_criterion.FastBIC}
UNSUPERVISED_SPLITTERS = {
    "best": _unsup_splitter.BestUnsupervisedSplitter,
}

UNSUPERVISED_OBLIQUE_SPLITTERS = {"best": _unsup_oblique_splitter.BestObliqueUnsupervisedSplitter}


class UnsupervisedDecisionTree(TransformerMixin, ClusterMixin, BaseDecisionTree):
    """Unsupervised decision tree.

    Parameters
    ----------
    criterion : {"twomeans", "fastbic"}, default="twomeans"
        The function to measure the quality of a split. Supported criteria are
        "twomeans" for the variance impurity and "fastbic" for the
        BIC criterion. If ``UnsupervisedCriterion`` instance is passed in, then
        the user must abide by the Cython internal API. See source code.
    splitter : {"best", "random"}, default="best"
        The strategy used to choose the split at each node. Supported
        strategies are "best" to choose the best split and "random" to choose
        the best random split. If ``UnsupervisedSplitter`` instance is passed in, then
        the user must abide by the Cython internal API. See source code.
    max_depth : int, default=None
        The maximum depth of the tree. If None, then nodes are expanded until
        all leaves are pure or until all leaves contain less than
        min_samples_split samples.
    min_samples_split : int or float, default=2
        The minimum number of samples required to split an internal node:

        - If int, then consider `min_samples_split` as the minimum number.
        - If float, then `min_samples_split` is a fraction and
          `ceil(min_samples_split * n_samples)` are the minimum
          number of samples for each split.
    min_samples_leaf : int or float, default=1
        The minimum number of samples required to be at a leaf node.
        A split point at any depth will only be considered if it leaves at
        least ``min_samples_leaf`` training samples in each of the left and
        right branches.  This may have the effect of smoothing the model,
        especially in regression.

        - If int, then consider `min_samples_leaf` as the minimum number.
        - If float, then `min_samples_leaf` is a fraction and
          `ceil(min_samples_leaf * n_samples)` are the minimum
          number of samples for each node.
    min_weight_fraction_leaf : float, default=0.0
        The minimum weighted fraction of the sum total of weights (of all
        the input samples) required to be at a leaf node. Samples have
        equal weight when sample_weight is not provided.
    max_features : int, float or {"auto", "sqrt", "log2"}, default=None
        The number of features to consider when looking for the best split:

            - If int, then consider `max_features` features at each split.
            - If float, then `max_features` is a fraction and
              `max(1, int(max_features * n_features_in_))` features are considered at
              each split.
            - If "auto", then `max_features=sqrt(n_features)`.
            - If "sqrt", then `max_features=sqrt(n_features)`.
            - If "log2", then `max_features=log2(n_features)`.
            - If None, then `max_features=n_features`.
    max_leaf_nodes : int, default=None
        Grow a tree with ``max_leaf_nodes`` in best-first fashion.
        Best nodes are defined as relative reduction in impurity.
        If None then unlimited number of leaf nodes.
    random_state : int, RandomState instance or None, default=None
        Controls the randomness of the estimator. The features are always
        randomly permuted at each split, even if ``splitter`` is set to
        ``"best"``. When ``max_features < n_features``, the algorithm will
        select ``max_features`` at random at each split before finding the best
        split among them. But the best found split may vary across different
        runs, even if ``max_features=n_features``. That is the case, if the
        improvement of the criterion is identical for several splits and one
        split has to be selected at random. To obtain a deterministic behaviour
        during fitting, ``random_state`` has to be fixed to an integer.
        See how scikit-learn defines ``random_state`` for details.
    min_impurity_decrease : float, default=0.0
        A node will be split if this split induces a decrease of the impurity
        greater than or equal to this value.

        The weighted impurity decrease equation is the following::

            N_t / N * (impurity - N_t_R / N_t * right_impurity
                                - N_t_L / N_t * left_impurity)

        where ``N`` is the total number of samples, ``N_t`` is the number of
        samples at the current node, ``N_t_L`` is the number of samples in the
        left child, and ``N_t_R`` is the number of samples in the right child.

        ``N``, ``N_t``, ``N_t_R`` and ``N_t_L`` all refer to the weighted sum,
        if ``sample_weight`` is passed.
    clustering_func : callable
        Scikit-learn compatible clustering function to take the affinity matrix
        and return cluster labels. By default, :class:`sklearn.cluster.AgglomerativeClustering`.
    clustering_func_args : dict
        Clustering function class keyword arguments. Passed to `clustering_func`.
    """

    def __init__(
        self,
        *,
        criterion="twomeans",
        splitter="best",
        max_depth=None,
        min_samples_split=5,
        min_samples_leaf=1,
        min_weight_fraction_leaf=0.0,
        max_features=None,
        max_leaf_nodes=None,
        random_state=None,
        min_impurity_decrease=0.0,
        clustering_func=None,
        clustering_func_args=None,
    ):
        super().__init__(
            criterion=criterion,
            splitter=splitter,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            min_samples_leaf=min_samples_leaf,
            min_weight_fraction_leaf=min_weight_fraction_leaf,
            max_features=max_features,
            max_leaf_nodes=max_leaf_nodes,
            random_state=random_state,
            min_impurity_decrease=min_impurity_decrease,
        )

        self.clustering_func = clustering_func
        self.clustering_func_args = clustering_func_args

    def fit(self, X, y=None, sample_weight=None, check_input=True):
        if check_input:
            # TODO: allow X to be sparse
            check_X_params = dict(dtype=DTYPE)  # , accept_sparse="csc"
            X = self._validate_data(X, validate_separately=(check_X_params))
            if issparse(X):
                X.sort_indices()

                if X.indices.dtype != np.intc or X.indptr.dtype != np.intc:
                    raise ValueError("No support for np.int64 index based sparse matrices")

        super().fit(X, None, sample_weight, check_input)

        # apply to the leaves
        n_samples = X.shape[0]
        X_leaves = self.apply(X)

        # now compute the affinity matrix and set it
        self.affinity_matrix_ = self._compute_affinity_matrix(X_leaves)

        # compute the labels and set it
        if n_samples >= 2:
            self.labels_ = self._assign_labels(self.affinity_matrix_)

        return self

    def _build_tree(
        self,
        X,
        y,
        sample_weight,
        min_samples_leaf,
        min_weight_leaf,
        max_leaf_nodes,
        min_samples_split,
        max_depth,
        random_state,
    ):
        criterion = self.criterion
        if not isinstance(criterion, UnsupervisedCriterion):
            criterion = UNSUPERVISED_CRITERIA[self.criterion]()
        else:
            # Make a deepcopy in case the criterion has mutable attributes that
            # might be shared and modified concurrently during parallel fitting
            criterion = copy.deepcopy(criterion)

        splitter = self.splitter
        if not isinstance(self.splitter, UnsupervisedSplitter):
            splitter = UNSUPERVISED_SPLITTERS[self.splitter](
                criterion,
                self.max_features_,
                min_samples_leaf,
                min_weight_leaf,
                random_state,
            )

        self.tree_ = UnsupervisedTree(self.n_features_in_)

        # Use BestFirst if max_leaf_nodes given; use DepthFirst otherwise
        if max_leaf_nodes < 0:
            builder = UnsupervisedDepthFirstTreeBuilder(
                splitter,
                min_samples_split,
                min_samples_leaf,
                min_weight_leaf,
                max_depth,
                self.min_impurity_decrease,
            )
        else:
            builder = UnsupervisedBestFirstTreeBuilder(
                splitter,
                min_samples_split,
                min_samples_leaf,
                min_weight_leaf,
                max_depth,
                max_leaf_nodes,
                self.min_impurity_decrease,
            )

        builder.build(self.tree_, X, sample_weight)

    def predict(self, X, check_input=True):
        """Assign labels based on clustering the affinity matrix.

        Parameters
        ----------
        X : array-like of shape (n_samples, n_features)
            Array to cluster.
        check_input : bool, optional
            Whether to validate input, by default True.

        Returns
        -------
        labels : array-like of shape (n_samples,)
            The assigned labels for each sample.
        """

        X = self._validate_X_predict(X, check_input=check_input)
        affinity_matrix = self.transform(X)

        # compute the labels and set it
        return self._assign_labels(affinity_matrix)

    def transform(self, X):
        """Transform X to a cluster-distance space.

        In the new space, each dimension is the distance to the cluster
        centers. Note that even if X is sparse, the array returned by
        `transform` will typically be dense.

        Parameters
        ----------
        X : {array-like, sparse matrix} of shape (n_samples, n_features)
            New data to transform.

        Returns
        -------
        X_new : ndarray of shape (n_samples, n_samples)
            X transformed in the new space.
        """
        check_is_fitted(self)
        # apply to the leaves
        X_leaves = self.apply(X)

        # now compute the affinity matrix and set it
        affinity_matrix = self._compute_affinity_matrix(X_leaves)
        return affinity_matrix

    def _compute_affinity_matrix(self, X_leaves):
        """Compute the proximity matrix of samples in X.

        Parameters
        ----------
        X_leaves : ndarray of shape (n_samples,)
            For each datapoint x in X and for each tree in the forest,
            is the index of the leaf x ends up in.

        Returns
        -------
        prox_matrix : array-like of shape (n_samples, n_samples)
        """
        n_samples = X_leaves.shape[0]
        aff_matrix = np.zeros((n_samples, n_samples), dtype=np.int32)

        # for every unique leaf in this dataset, count all co-occurrences of samples
        # in the same leaf
        for leaf in np.unique(X_leaves):
            # find out which samples occur with this leaf
            samples_in_leaf = np.atleast_1d(np.argwhere(X_leaves == leaf).squeeze())
            aff_matrix[np.ix_(samples_in_leaf, samples_in_leaf)] += 1

        return aff_matrix

    def _assign_labels(self, affinity_matrix):
        """Assign cluster labels given X.

        Parameters
        ----------
        X : ndarray of shape (n_samples, n_samples)
            The affinity matrix.

        Returns
        -------
        predict_labels : ndarray of shape (n_samples,)
            The predicted cluster labels
        """
        if self.clustering_func is None:
            self.clustering_func_ = AgglomerativeClustering
        else:
            self.clustering_func_ = self.clustering_func
        if self.clustering_func_args is None:
            self.clustering_func_args_ = dict()
        else:
            self.clustering_func_args_ = self.clustering_func_args
        cluster = self.clustering_func_(**self.clustering_func_args_)

        # apply agglomerative clustering to obtain cluster labels
        predict_labels = cluster.fit_predict(affinity_matrix)
        return predict_labels


class UnsupervisedObliqueDecisionTree(UnsupervisedDecisionTree):
    """Unsupervised oblique decision tree.

    Parameters
    ----------
    criterion : {"twomeans", "fastbic"}, default="twomeans"
        The function to measure the quality of a split. Supported criteria are
        "twomeans" for the variance impurity and "fastbic" for the
        BIC criterion. If ``UnsupervisedCriterion`` instance is passed in, then
        the user must abide by the Cython internal API. See source code.
    splitter : {"best", "random"}, default="best"
        The strategy used to choose the split at each node. Supported
        strategies are "best" to choose the best split and "random" to choose
        the best random split. If ``UnsupervisedSplitter`` instance is passed in, then
        the user must abide by the Cython internal API. See source code.
    max_depth : int, default=None
        The maximum depth of the tree. If None, then nodes are expanded until
        all leaves are pure or until all leaves contain less than
        min_samples_split samples.
    min_samples_split : int or float, default=2
        The minimum number of samples required to split an internal node:

        - If int, then consider `min_samples_split` as the minimum number.
        - If float, then `min_samples_split` is a fraction and
          `ceil(min_samples_split * n_samples)` are the minimum
          number of samples for each split.
    min_samples_leaf : int or float, default=1
        The minimum number of samples required to be at a leaf node.
        A split point at any depth will only be considered if it leaves at
        least ``min_samples_leaf`` training samples in each of the left and
        right branches.  This may have the effect of smoothing the model,
        especially in regression.

        - If int, then consider `min_samples_leaf` as the minimum number.
        - If float, then `min_samples_leaf` is a fraction and
          `ceil(min_samples_leaf * n_samples)` are the minimum
          number of samples for each node.
    min_weight_fraction_leaf : float, default=0.0
        The minimum weighted fraction of the sum total of weights (of all
        the input samples) required to be at a leaf node. Samples have
        equal weight when sample_weight is not provided.
    max_features : int, float or {"auto", "sqrt", "log2"}, default=None
        The number of features to consider when looking for the best split:

            - If int, then consider `max_features` features at each split.
            - If float, then `max_features` is a fraction and
              `max(1, int(max_features * n_features_in_))` features are considered at
              each split.
            - If "auto", then `max_features=sqrt(n_features)`.
            - If "sqrt", then `max_features=sqrt(n_features)`.
            - If "log2", then `max_features=log2(n_features)`.
            - If None, then `max_features=n_features`.
    max_leaf_nodes : int, default=None
        Grow a tree with ``max_leaf_nodes`` in best-first fashion.
        Best nodes are defined as relative reduction in impurity.
        If None then unlimited number of leaf nodes.
    random_state : int, RandomState instance or None, default=None
        Controls the randomness of the estimator. The features are always
        randomly permuted at each split, even if ``splitter`` is set to
        ``"best"``. When ``max_features < n_features``, the algorithm will
        select ``max_features`` at random at each split before finding the best
        split among them. But the best found split may vary across different
        runs, even if ``max_features=n_features``. That is the case, if the
        improvement of the criterion is identical for several splits and one
        split has to be selected at random. To obtain a deterministic behaviour
        during fitting, ``random_state`` has to be fixed to an integer.
        See how scikit-learn defines ``random_state`` for details.
    min_impurity_decrease : float, default=0.0
        A node will be split if this split induces a decrease of the impurity
        greater than or equal to this value.

        The weighted impurity decrease equation is the following::

            N_t / N * (impurity - N_t_R / N_t * right_impurity
                                - N_t_L / N_t * left_impurity)

        where ``N`` is the total number of samples, ``N_t`` is the number of
        samples at the current node, ``N_t_L`` is the number of samples in the
        left child, and ``N_t_R`` is the number of samples in the right child.

        ``N``, ``N_t``, ``N_t_R`` and ``N_t_L`` all refer to the weighted sum,
        if ``sample_weight`` is passed.
    feature_combinations : float, default=1.5
        The number of features to combine on average at each split
        of the decision trees.
    clustering_func : callable
        Scikit-learn compatible clustering function to take the affinity matrix
        and return cluster labels. By default, :class:`sklearn.cluster.AgglomerativeClustering`.
    clustering_func_args : dict
        Clustering function class keyword arguments. Passed to `clustering_func`.
    """

    def __init__(
        self,
        *,
        criterion="twomeans",
        splitter="best",
        max_depth=None,
        min_samples_split=5,
        min_samples_leaf=1,
        min_weight_fraction_leaf=0,
        max_features=None,
        max_leaf_nodes=None,
        random_state=None,
        min_impurity_decrease=0,
        feature_combinations=1.5,
        clustering_func=None,
        clustering_func_args=None,
    ):
        super().__init__(
            criterion=criterion,
            splitter=splitter,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            min_samples_leaf=min_samples_leaf,
            min_weight_fraction_leaf=min_weight_fraction_leaf,
            max_features=max_features,
            max_leaf_nodes=max_leaf_nodes,
            random_state=random_state,
            min_impurity_decrease=min_impurity_decrease,
            clustering_func=clustering_func,
            clustering_func_args=clustering_func_args,
        )
        self.feature_combinations = feature_combinations

    def _build_tree(
        self,
        X,
        y,
        sample_weight,
        min_samples_leaf,
        min_weight_leaf,
        max_leaf_nodes,
        min_samples_split,
        max_depth,
        random_state,
    ):
        # TODO: add feature_combinations fix that was used in obliquedecisiontreeclassifier

        criterion = self.criterion
        if not isinstance(criterion, UnsupervisedCriterion):
            criterion = UNSUPERVISED_CRITERIA[self.criterion]()
        else:
            # Make a deepcopy in case the criterion has mutable attributes that
            # might be shared and modified concurrently during parallel fitting
            criterion = copy.deepcopy(criterion)

        splitter = self.splitter
        if not isinstance(self.splitter, UnsupervisedObliqueSplitter):
            splitter = UNSUPERVISED_OBLIQUE_SPLITTERS[self.splitter](
                criterion,
                self.max_features_,
                min_samples_leaf,
                min_weight_leaf,
                random_state,
                self.feature_combinations,
            )

        self.tree_ = UnsupervisedObliqueTree(self.n_features_in_)

        # Use BestFirst if max_leaf_nodes given; use DepthFirst otherwise
        if max_leaf_nodes < 0:
            builder = UnsupervisedDepthFirstTreeBuilder(
                splitter,
                min_samples_split,
                min_samples_leaf,
                min_weight_leaf,
                max_depth,
                self.min_impurity_decrease,
            )
        else:
            builder = UnsupervisedBestFirstTreeBuilder(
                splitter,
                min_samples_split,
                min_samples_leaf,
                min_weight_leaf,
                max_depth,
                max_leaf_nodes,
                self.min_impurity_decrease,
            )

        builder.build(self.tree_, X, sample_weight)


class ObliqueDecisionTreeClassifier(DecisionTreeClassifier):
    """A decision tree classifier.

    Read more in the :ref:`User Guide <sklearn:tree>`.

    Parameters
    ----------
    criterion : {"gini", "entropy"}, default="gini"
        The function to measure the quality of a split. Supported criteria are
        "gini" for the Gini impurity and "entropy" for the information gain.

    splitter : {"best", "random"}, default="best"
        The strategy used to choose the split at each node. Supported
        strategies are "best" to choose the best split and "random" to choose
        the best random split.

    max_depth : int, default=None
        The maximum depth of the tree. If None, then nodes are expanded until
        all leaves are pure or until all leaves contain less than
        min_samples_split samples.

    min_samples_split : int or float, default=2
        The minimum number of samples required to split an internal node:

        - If int, then consider `min_samples_split` as the minimum number.
        - If float, then `min_samples_split` is a fraction and
          `ceil(min_samples_split * n_samples)` are the minimum
          number of samples for each split.

    min_samples_leaf : int or float, default=1
        The minimum number of samples required to be at a leaf node.
        A split point at any depth will only be considered if it leaves at
        least ``min_samples_leaf`` training samples in each of the left and
        right branches.  This may have the effect of smoothing the model,
        especially in regression.

        - If int, then consider `min_samples_leaf` as the minimum number.
        - If float, then `min_samples_leaf` is a fraction and
          `ceil(min_samples_leaf * n_samples)` are the minimum
          number of samples for each node.

    min_weight_fraction_leaf : float, default=0.0
        The minimum weighted fraction of the sum total of weights (of all
        the input samples) required to be at a leaf node. Samples have
        equal weight when sample_weight is not provided.

    max_features : int, float or {"auto", "sqrt", "log2"}, default=None
        The number of features to consider when looking for the best split:

            - If int, then consider `max_features` features at each split.
            - If float, then `max_features` is a fraction and
              `int(max_features * n_features)` features are considered at each
              split.
            - If "auto", then `max_features=sqrt(n_features)`.
            - If "sqrt", then `max_features=sqrt(n_features)`.
            - If "log2", then `max_features=log2(n_features)`.
            - If None, then `max_features=n_features`.

        Note: the search for a split does not stop until at least one
        valid partition of the node samples is found, even if it requires to
        effectively inspect more than ``max_features`` features.

        Note: Compared to axis-aligned Random Forests, one can set
        max_features to a number greater then ``n_features``.

    random_state : int, RandomState instance or None, default=None
        Controls the randomness of the estimator. The features are always
        randomly permuted at each split, even if ``splitter`` is set to
        ``"best"``. When ``max_features < n_features``, the algorithm will
        select ``max_features`` at random at each split before finding the best
        split among them. But the best found split may vary across different
        runs, even if ``max_features=n_features``. That is the case, if the
        improvement of the criterion is identical for several splits and one
        split has to be selected at random. To obtain a deterministic behaviour
        during fitting, ``random_state`` has to be fixed to an integer.
        See :term:`Glossary <random_state>` for details.

    max_leaf_nodes : int, default=None
        Grow a tree with ``max_leaf_nodes`` in best-first fashion.
        Best nodes are defined as relative reduction in impurity.
        If None then unlimited number of leaf nodes.

    min_impurity_decrease : float, default=0.0
        A node will be split if this split induces a decrease of the impurity
        greater than or equal to this value.

        The weighted impurity decrease equation is the following::

            N_t / N * (impurity - N_t_R / N_t * right_impurity
                                - N_t_L / N_t * left_impurity)

        where ``N`` is the total number of samples, ``N_t`` is the number of
        samples at the current node, ``N_t_L`` is the number of samples in the
        left child, and ``N_t_R`` is the number of samples in the right child.

        ``N``, ``N_t``, ``N_t_R`` and ``N_t_L`` all refer to the weighted sum,
        if ``sample_weight`` is passed.

    class_weight : dict, list of dict or "balanced", default=None
        Weights associated with classes in the form ``{class_label: weight}``.
        If None, all classes are supposed to have weight one. For
        multi-output problems, a list of dicts can be provided in the same
        order as the columns of y.

        Note that for multioutput (including multilabel) weights should be
        defined for each class of every column in its own dict. For example,
        for four-class multilabel classification weights should be
        [{0: 1, 1: 1}, {0: 1, 1: 5}, {0: 1, 1: 1}, {0: 1, 1: 1}] instead of
        [{1:1}, {2:5}, {3:1}, {4:1}].

        The "balanced" mode uses the values of y to automatically adjust
        weights inversely proportional to class frequencies in the input data
        as ``n_samples / (n_classes * np.bincount(y))``

        For multi-output, the weights of each column of y will be multiplied.

        Note that these weights will be multiplied with sample_weight (passed
        through the fit method) if sample_weight is specified.

    feature_combinations : float, default=None
        The number of features to combine on average at each split
        of the decision trees. If ``None``, then will default to the minimum of
        ``(1.5, n_features)``. This controls the number of non-zeros is the
        projection matrix. Setting the value to 1.0 is equivalent to a
        traditional decision-tree. ``feature_combinations * max_features``
        gives the number of expected non-zeros in the projection matrix of shape
        ``(max_features, n_features)``. Thus this value must always be less than
        ``n_features`` in order to be valid.

    Attributes
    ----------
    classes_ : ndarray of shape (n_classes,) or list of ndarray
        The classes labels (single output problem),
        or a list of arrays of class labels (multi-output problem).

    feature_importances_ : ndarray of shape (n_features,)
        The impurity-based feature importances.
        The higher, the more important the feature.
        The importance of a feature is computed as the (normalized)
        total reduction of the criterion brought by that feature.  It is also
        known as the Gini importance [4]_.

        Warning: impurity-based feature importances can be misleading for
        high cardinality features (many unique values). See
        :func:`sklearn.inspection.permutation_importance` as an alternative.

    max_features_ : int
        The inferred value of max_features.

    n_classes_ : int or list of int
        The number of classes (for single output problems),
        or a list containing the number of classes for each
        output (for multi-output problems).

    n_features_in_ : int
        Number of features seen during :term:`fit`.

    feature_names_in_ : ndarray of shape (`n_features_in_`,)
        Names of features seen during :term:`fit`. Defined only when `X`
        has feature names that are all strings.

    n_outputs_ : int
        The number of outputs when ``fit`` is performed.

    tree_ : Tree instance
        The underlying Tree object. Please refer to
        ``help(sklearn.tree._tree.Tree)`` for
        attributes of Tree object.

    feature_combinations_ : float
        The number of feature combinations on average taken to fit the tree.

    See Also
    --------
    DecisionTreeClassifier : An axis-aligned decision tree classifier.

    Notes
    -----
    Compared to ``DecisionTreeClassifier``, oblique trees can sample
    more features then ``n_features``, where ``n_features`` is the number
    of columns in ``X``. This is controlled via the ``max_features``
    parameter. In fact, sampling more times results in better
    trees with the caveat that there is an increased computation. It is
    always recommended to sample more if one is willing to spend the
    computational resources.

    The default values for the parameters controlling the size of the trees
    (e.g. ``max_depth``, ``min_samples_leaf``, etc.) lead to fully grown and
    unpruned trees which can potentially be very large on some data sets. To
    reduce memory consumption, the complexity and size of the trees should be
    controlled by setting those parameter values.

    The :meth:`predict` method operates using the :func:`numpy.argmax`
    function on the outputs of :meth:`predict_proba`. This means that in
    case the highest predicted probabilities are tied, the classifier will
    predict the tied class with the lowest index in :term:`classes_`.

    References
    ----------

    .. [1] https://en.wikipedia.org/wiki/Decision_tree_learning

    .. [2] L. Breiman, J. Friedman, R. Olshen, and C. Stone, "Classification
        and Regression Trees", Wadsworth, Belmont, CA, 1984.

    .. [3] T. Hastie, R. Tibshirani and J. Friedman. "Elements of Statistical
        Learning", Springer, 2009.

    .. [4] L. Breiman, and A. Cutler, "Random Forests",
        https://www.stat.berkeley.edu/~breiman/RandomForests/cc_home.htm

    Examples
    --------
    >>> from sklearn.datasets import load_iris
    >>> from sklearn.model_selection import cross_val_score
    >>> from sktree.tree import ObliqueDecisionTreeClassifier
    >>> clf = ObliqueDecisionTreeClassifier(random_state=0)
    >>> iris = load_iris()
    >>> cross_val_score(clf, iris.data, iris.target, cv=10)
    ...                             # doctest: +SKIP
    ...
    array([ 1.     ,  0.93...,  0.86...,  0.93...,  0.93...,
            0.93...,  0.93...,  1.     ,  0.93...,  1.      ])
    """

    _parameter_constraints = {
        **DecisionTreeClassifier._parameter_constraints,
        "feature_combinations": [
            Interval(Real, 1.0, None, closed="left"),
            None,
        ],
    }

    def __init__(
        self,
        *,
        criterion="gini",
        splitter="best",
        max_depth=None,
        min_samples_split=2,
        min_samples_leaf=1,
        min_weight_fraction_leaf=0.0,
        max_features=None,
        random_state=None,
        max_leaf_nodes=None,
        min_impurity_decrease=0.0,
        class_weight=None,
        feature_combinations=None,
    ):
        super().__init__(
            criterion=criterion,
            splitter=splitter,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            min_samples_leaf=min_samples_leaf,
            min_weight_fraction_leaf=min_weight_fraction_leaf,
            max_features=max_features,
            max_leaf_nodes=max_leaf_nodes,
            class_weight=class_weight,
            random_state=random_state,
            min_impurity_decrease=min_impurity_decrease,
        )

        self.feature_combinations = feature_combinations

    def _build_tree(
        self,
        X,
        y,
        sample_weight,
        min_samples_leaf,
        min_weight_leaf,
        max_leaf_nodes,
        min_samples_split,
        max_depth,
        random_state,
    ):
        """Build the actual tree.

        Parameters
        ----------
        X : {array-like, sparse matrix} of shape (n_samples, n_features)
            The training input samples. Internally, it will be converted to
            ``dtype=np.float32`` and if a sparse matrix is provided
            to a sparse ``csc_matrix``.
        y : array-like of shape (n_samples,) or (n_samples, n_outputs)
            The target values (class labels) as integers or strings.
        sample_weight : array-like of shape (n_samples,), default=None
            Sample weights. If None, then samples are equally weighted. Splits
            that would create child nodes with net zero or negative weight are
            ignored while searching for a split in each node. Splits are also
            ignored if they would result in any single class carrying a
            negative weight in either child node.
        min_samples_leaf : int or float
            The minimum number of samples required to be at a leaf node.
        min_weight_leaf : float, default=0.0
           The minimum weighted fraction of the sum total of weights.
        max_leaf_nodes : int, default=None
            Grow a tree with ``max_leaf_nodes`` in best-first fashion.
        min_samples_split : int or float, default=2
            The minimum number of samples required to split an internal node:
        max_depth : int, default=None
            The maximum depth of the tree. If None, then nodes are expanded until
            all leaves are pure or until all leaves contain less than
            min_samples_split samples.
        random_state : int, RandomState instance or None, default=None
            Controls the randomness of the estimator.
        """
        n_samples, n_features = X.shape

        if self.feature_combinations is None:
            self.feature_combinations_ = min(n_features, 1.5)
        elif self.feature_combinations > n_features:
            raise RuntimeError(
                f"Feature combinations {self.feature_combinations} should not be "
                f"greater than the possible number of features {n_features}"
            )
        else:
            self.feature_combinations_ = self.feature_combinations

        # Build tree
        criterion = self.criterion
        if not isinstance(criterion, BaseCriterion):
            if is_classifier(self):
                criterion = CRITERIA_CLF[self.criterion](self.n_outputs_, self.n_classes_)
            else:
                criterion = CRITERIA_REG[self.criterion](self.n_outputs_, n_samples)
        else:
            # Make a deepcopy in case the criterion has mutable attributes that
            # might be shared and modified concurrently during parallel fitting
            criterion = copy.deepcopy(criterion)

        splitter = self.splitter
        if issparse(X):
            raise ValueError(
                "Sparse input is not supported for oblique trees. "
                "Please convert your data to a dense array."
            )
        else:
            OBLIQUE_SPLITTERS = OBLIQUE_DENSE_SPLITTERS

        if not isinstance(self.splitter, ObliqueSplitter):
            splitter = OBLIQUE_SPLITTERS[self.splitter](
                criterion,
                self.max_features_,
                min_samples_leaf,
                min_weight_leaf,
                random_state,
                self.feature_combinations_,
            )

        if is_classifier(self):
            self.tree_ = ObliqueTree(self.n_features_in_, self.n_classes_, self.n_outputs_)
        else:
            self.tree_ = ObliqueTree(
                self.n_features_in_,
                # TODO: tree shouldn't need this in this case
                np.array([1] * self.n_outputs_, dtype=np.intp),
                self.n_outputs_,
            )

        # Use BestFirst if max_leaf_nodes given; use DepthFirst otherwise
        if max_leaf_nodes < 0:
            builder = DepthFirstTreeBuilder(
                splitter,
                min_samples_split,
                min_samples_leaf,
                min_weight_leaf,
                max_depth,
                self.min_impurity_decrease,
            )
        else:
            builder = BestFirstTreeBuilder(
                splitter,
                min_samples_split,
                min_samples_leaf,
                min_weight_leaf,
                max_depth,
                max_leaf_nodes,
                self.min_impurity_decrease,
            )

        builder.build(self.tree_, X, y, sample_weight)

        if self.n_outputs_ == 1 and is_classifier(self):
            self.n_classes_ = self.n_classes_[0]
            self.classes_ = self.classes_[0]


class PatchObliqueDecisionTreeClassifier(DecisionTreeClassifier):
    """A oblique decision tree classifier that operates over patches of data.

    A patch oblique decision tree is also known as a manifold oblique decision tree
    (called MORF in :footcite:`Li2019manifold`), where the splitter is aware of
    the structure in the data. For example, in an image, a patch would be contiguous
    along the rows and columns of the image. In a multivariate time-series, a patch
    would be contiguous over time, but possibly discontiguous over the sensors.

    Parameters
    ----------
    criterion : {"gini", "entropy"}, default="gini"
        The function to measure the quality of a split. Supported criteria are
        "gini" for the Gini impurity and "entropy" for the information gain.

    splitter : {"best", "random"}, default="best"
        The strategy used to choose the split at each node. Supported
        strategies are "best" to choose the best split and "random" to choose
        the best random split.

    max_depth : int, default=None
        The maximum depth of the tree. If None, then nodes are expanded until
        all leaves are pure or until all leaves contain less than
        min_samples_split samples.

    min_samples_split : int or float, default=2
        The minimum number of samples required to split an internal node:

        - If int, then consider `min_samples_split` as the minimum number.
        - If float, then `min_samples_split` is a fraction and
          `ceil(min_samples_split * n_samples)` are the minimum
          number of samples for each split.

    min_samples_leaf : int or float, default=1
        The minimum number of samples required to be at a leaf node.
        A split point at any depth will only be considered if it leaves at
        least ``min_samples_leaf`` training samples in each of the left and
        right branches.  This may have the effect of smoothing the model,
        especially in regression.

        - If int, then consider `min_samples_leaf` as the minimum number.
        - If float, then `min_samples_leaf` is a fraction and
          `ceil(min_samples_leaf * n_samples)` are the minimum
          number of samples for each node.

    min_weight_fraction_leaf : float, default=0.0
        The minimum weighted fraction of the sum total of weights (of all
        the input samples) required to be at a leaf node. Samples have
        equal weight when sample_weight is not provided.

    max_features : int, float or {"auto", "sqrt", "log2"}, default=None
        The number of features to consider when looking for the best split:

            - If int, then consider `max_features` features at each split.
            - If float, then `max_features` is a fraction and
              `int(max_features * n_features)` features are considered at each
              split.
            - If "auto", then `max_features=sqrt(n_features)`.
            - If "sqrt", then `max_features=sqrt(n_features)`.
            - If "log2", then `max_features=log2(n_features)`.
            - If None, then `max_features=n_features`.

        Note: the search for a split does not stop until at least one
        valid partition of the node samples is found, even if it requires to
        effectively inspect more than ``max_features`` features.

        Note: Compared to axis-aligned Random Forests, one can set
        max_features to a number greater then ``n_features``.

    random_state : int, RandomState instance or None, default=None
        Controls the randomness of the estimator. The features are always
        randomly permuted at each split, even if ``splitter`` is set to
        ``"best"``. When ``max_features < n_features``, the algorithm will
        select ``max_features`` at random at each split before finding the best
        split among them. But the best found split may vary across different
        runs, even if ``max_features=n_features``. That is the case, if the
        improvement of the criterion is identical for several splits and one
        split has to be selected at random. To obtain a deterministic behaviour
        during fitting, ``random_state`` has to be fixed to an integer.
        See :term:`Glossary <random_state>` for details.

    max_leaf_nodes : int, default=None
        Grow a tree with ``max_leaf_nodes`` in best-first fashion.
        Best nodes are defined as relative reduction in impurity.
        If None then unlimited number of leaf nodes.

    min_impurity_decrease : float, default=0.0
        A node will be split if this split induces a decrease of the impurity
        greater than or equal to this value.

        The weighted impurity decrease equation is the following::

            N_t / N * (impurity - N_t_R / N_t * right_impurity
                                - N_t_L / N_t * left_impurity)

        where ``N`` is the total number of samples, ``N_t`` is the number of
        samples at the current node, ``N_t_L`` is the number of samples in the
        left child, and ``N_t_R`` is the number of samples in the right child.

        ``N``, ``N_t``, ``N_t_R`` and ``N_t_L`` all refer to the weighted sum,
        if ``sample_weight`` is passed.

    class_weight : dict, list of dict or "balanced", default=None
        Weights associated with classes in the form ``{class_label: weight}``.
        If None, all classes are supposed to have weight one. For
        multi-output problems, a list of dicts can be provided in the same
        order as the columns of y.

        Note that for multioutput (including multilabel) weights should be
        defined for each class of every column in its own dict. For example,
        for four-class multilabel classification weights should be
        [{0: 1, 1: 1}, {0: 1, 1: 5}, {0: 1, 1: 1}, {0: 1, 1: 1}] instead of
        [{1:1}, {2:5}, {3:1}, {4:1}].

        The "balanced" mode uses the values of y to automatically adjust
        weights inversely proportional to class frequencies in the input data
        as ``n_samples / (n_classes * np.bincount(y))``

        For multi-output, the weights of each column of y will be multiplied.

        Note that these weights will be multiplied with sample_weight (passed
        through the fit method) if sample_weight is specified.
    min_patch_height : int, optional
        The minimum height of a patch, by default 1.
    max_patch_height : int, optional
        The maximum height of a patch, by default 1.
    min_patch_width : int, optional
        The minimum width of a patch, by default 1.
    max_patch_width : int, optional
        The maximum width of a patch, by default 1.
    data_height : int, optional
        The presumed height of the un-vectorized feature vector, by default 1.
    data_width : int, optional
        The presumed height of the un-vectorized feature vector, by default None.
        If None, the data width will be presumed the number of columns in ``X``
        passed to :meth:`fit`.

    Notes
    -----
    Patches are 2D masks that are applied onto the data matrix. Following sklearn
    API standards, ``X`` is always a ``(n_samples, n_features)`` array even if
    X is comprised of images, or multivariate-time series. The ``data_width`` and
    ``data_height`` parameters are used to inform the ``PatchObliqueDecisionTreeClassifier``
    of the original structure of the data. It is required that
    ``data_width * data_height = n_features``.

    When users pass in ``X`` to :meth:`fit`, tt is presumed that all vectorization operations
    are done C-contiguously (i.e. the last axis is contiguous).

    Note that for a patch height and width of size 1, the tree is exactly the same as the
    decision tree, albeit with less efficiency optimizations. Therefore, it is always
    recommended to set the range of patch heights and widths based on the structure of your
    expected input data.

    References
    ----------
    .. footbibliography::
    """

    _parameter_constraints = {
        **DecisionTreeClassifier._parameter_constraints,
        "min_patch_height": [Interval(Integral, 1, None, closed="left")],
        "max_patch_height": [Interval(Integral, 1, None, closed="left")],
        "min_patch_width": [Interval(Integral, 1, None, closed="left")],
        "max_patch_width": [Interval(Integral, 1, None, closed="left")],
        "data_width": [Interval(Integral, 1, None, closed="left"), None],
        "data_height": [Interval(Integral, 1, None, closed="left")],
    }

    def __init__(
        self,
        *,
        criterion="gini",
        splitter="best",
        max_depth=None,
        min_samples_split=2,
        min_samples_leaf=1,
        min_weight_fraction_leaf=0.0,
        max_features=None,
        random_state=None,
        max_leaf_nodes=None,
        min_impurity_decrease=0.0,
        class_weight=None,
        min_patch_height=1,
        max_patch_height=1,
        min_patch_width=1,
        max_patch_width=1,
        data_height=1,
        data_width=None,
    ):
        super().__init__(
            criterion=criterion,
            splitter=splitter,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            min_samples_leaf=min_samples_leaf,
            min_weight_fraction_leaf=min_weight_fraction_leaf,
            max_features=max_features,
            max_leaf_nodes=max_leaf_nodes,
            class_weight=class_weight,
            random_state=random_state,
            min_impurity_decrease=min_impurity_decrease,
        )

        self.min_patch_height = min_patch_height
        self.max_patch_height = max_patch_height
        self.min_patch_width = min_patch_width
        self.max_patch_width = max_patch_width
        self.data_height = data_height
        self.data_width = data_width

    def fit(self, X, y, sample_weight=None, check_input=True):
        """Fit tree.

        Parameters
        ----------
        X : {array-like, sparse matrix} of shape (n_samples, n_features)
            The training input samples. Internally, it will be converted to
            ``dtype=np.float32`` and if a sparse matrix is provided
            to a sparse ``csc_matrix``.
        y : array-like of shape (n_samples,) or (n_samples, n_outputs)
            The target values (class labels) as integers or strings.
        sample_weight : array-like of shape (n_samples,), default=None
            Sample weights. If None, then samples are equally weighted. Splits
            that would create child nodes with net zero or negative weight are
            ignored while searching for a split in each node. Splits are also
            ignored if they would result in any single class carrying a
            negative weight in either child node.
        check_input : bool, optional
            Whether or not to check input, by default True.
        """

        if check_input:
            # Need to validate separately here.
            # We can't pass multi_output=True because that would allow y to be
            # csr.
            check_X_params = dict(dtype=DTYPE, accept_sparse="csc")
            check_y_params = dict(ensure_2d=False, dtype=None)
            if y is not None:
                X, y = self._validate_data(
                    X, y, validate_separately=(check_X_params, check_y_params)
                )
            else:
                X = self._validate_data(X, **check_X_params)
            if issparse(X):
                X.sort_indices()

                if X.indices.dtype != np.intc or X.indptr.dtype != np.intc:
                    raise ValueError("No support for np.int64 index based sparse matrices")

            if y is not None and self.criterion == "poisson":
                if np.any(y < 0):
                    raise ValueError(
                        "Some value(s) of y are negative which is"
                        " not allowed for Poisson regression."
                    )
                if np.sum(y) <= 0:
                    raise ValueError(
                        "Sum of y is not positive which is " "necessary for Poisson regression."
                    )

        # validate data height/width
        if self.data_width is None:
            self.data_width_ = X.shape[1]
        else:
            self.data_width_ = self.data_width
        self.data_height_ = self.data_height

        if self.data_height_ * self.data_width_ != X.shape[1]:
            raise RuntimeError(
                f"The passed in data height ({self.data_height}) and "
                f"width ({self.data_width}) does not equal the number of "
                f"columns in X ({X.shape[1]})"
            )

        # validate patch parameters
        if self.min_patch_height > self.max_patch_height:
            raise RuntimeError(
                f"The minimum patch height {self.min_patch_height} is "
                f"greater than the maximum patch height {self.max_patch_height}"
            )
        if self.min_patch_width > self.max_patch_width:
            raise RuntimeError(
                f"The minimum patch width {self.min_patch_width} is "
                f"greater than the maximum patch width {self.max_patch_width}"
            )
        if self.max_patch_width > self.data_width_:
            raise RuntimeError(
                f"The maximum patch width {self.max_patch_width} is "
                f"greater than the data width {self.data_width_}"
            )
        if self.max_patch_height > self.data_height_:
            raise RuntimeError(
                f"The maximum patch height {self.max_patch_height} is "
                f"greater than the data height {self.data_height_}"
            )

        return super().fit(X, y, sample_weight, check_input=False)

    def _build_tree(
        self,
        X,
        y,
        sample_weight,
        min_samples_leaf,
        min_weight_leaf,
        max_leaf_nodes,
        min_samples_split,
        max_depth,
        random_state,
    ):
        """Build the actual tree.

        Parameters
        ----------
        X : {array-like, sparse matrix} of shape (n_samples, n_features)
            The training input samples. Internally, it will be converted to
            ``dtype=np.float32`` and if a sparse matrix is provided
            to a sparse ``csc_matrix``.
        y : array-like of shape (n_samples,) or (n_samples, n_outputs)
            The target values (class labels) as integers or strings.
        sample_weight : array-like of shape (n_samples,), default=None
            Sample weights. If None, then samples are equally weighted. Splits
            that would create child nodes with net zero or negative weight are
            ignored while searching for a split in each node. Splits are also
            ignored if they would result in any single class carrying a
            negative weight in either child node.
        min_samples_leaf : int or float
            The minimum number of samples required to be at a leaf node.
        min_weight_leaf : float, default=0.0
           The minimum weighted fraction of the sum total of weights.
        max_leaf_nodes : int, default=None
            Grow a tree with ``max_leaf_nodes`` in best-first fashion.
        min_samples_split : int or float, default=2
            The minimum number of samples required to split an internal node:
        max_depth : int, default=None
            The maximum depth of the tree. If None, then nodes are expanded until
            all leaves are pure or until all leaves contain less than
            min_samples_split samples.
        random_state : int, RandomState instance or None, default=None
            Controls the randomness of the estimator.
        """

        n_samples = X.shape[0]

        # Build tree
        criterion = self.criterion
        if not isinstance(criterion, BaseCriterion):
            if is_classifier(self):
                criterion = CRITERIA_CLF[self.criterion](self.n_outputs_, self.n_classes_)
            else:
                criterion = CRITERIA_REG[self.criterion](self.n_outputs_, n_samples)
        else:
            # Make a deepcopy in case the criterion has mutable attributes that
            # might be shared and modified concurrently during parallel fitting
            criterion = copy.deepcopy(criterion)

        splitter = self.splitter
        if issparse(X):
            raise ValueError(
                "Sparse input is not supported for oblique trees. "
                "Please convert your data to a dense array."
            )
        else:
            PATCH_SPLITTERS = PATCH_DENSE_SPLITTERS

        if not isinstance(self.splitter, PatchSplitter):
            splitter = PATCH_SPLITTERS[self.splitter](
                criterion,
                self.max_features_,
                min_samples_leaf,
                min_weight_leaf,
                random_state,
                self.min_patch_height,
                self.max_patch_height,
                self.min_patch_width,
                self.max_patch_width,
                self.data_height_,
                self.data_width_,
            )

        if is_classifier(self):
            self.tree_ = ObliqueTree(self.n_features_in_, self.n_classes_, self.n_outputs_)
        else:
            self.tree_ = ObliqueTree(
                self.n_features_in_,
                # TODO: tree shouldn't need this in this case
                np.array([1] * self.n_outputs_, dtype=np.intp),
                self.n_outputs_,
            )

        # Use BestFirst if max_leaf_nodes given; use DepthFirst otherwise
        if max_leaf_nodes < 0:
            builder = DepthFirstTreeBuilder(
                splitter,
                min_samples_split,
                min_samples_leaf,
                min_weight_leaf,
                max_depth,
                self.min_impurity_decrease,
            )
        else:
            builder = BestFirstTreeBuilder(
                splitter,
                min_samples_split,
                min_samples_leaf,
                min_weight_leaf,
                max_depth,
                max_leaf_nodes,
                self.min_impurity_decrease,
            )

        builder.build(self.tree_, X, y, sample_weight)

        if self.n_outputs_ == 1 and is_classifier(self):
            self.n_classes_ = self.n_classes_[0]
            self.classes_ = self.classes_[0]
