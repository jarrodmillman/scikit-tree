import numpy as np
cimport numpy as cnp
cnp.import_array()

cdef class UnsupervisedCriterion(BaseCriterion):
    """Abstract criterion for unsupervised learning.
    
    This object is a copy of the Criterion class of scikit-learn, but is used
    for unsupervised learning. However, ``Criterion`` in scikit-learn was
    designed for supervised learning, where the necessary
    ingredients to compute a split point is solely with y-labels. In
    this object, we subclass and instead rely on the X-data.    

    This object stores methods on how to calculate how good a split is using
    different metrics for unsupervised splitting.
    """
    cdef int init(
        self,
        const DOUBLE_t[:, ::1] X,
        const DOUBLE_t[:] sample_weight,
        double weighted_n_samples,
        const SIZE_t[:] sample_indices
    ) nogil except -1:
        """Initialize the criterion.

        This initializes the criterion at node samples[start:end] and children
        samples[start:start] and samples[start:end].

        Returns -1 in case of failure to allocate memory (and raise MemoryError)
        or 0 otherwise.

        Parameters
        ----------
        X : array-like, dtype=DOUBLE_t
            The data-feature matrix stored as a buffer for memory efficiency. Note that
            this is not used, but simply passed as a convenience function.
        sample_weight : array-like, dtype=DOUBLE_t
            The weight of each sample (i.e. row of X).
        weighted_n_samples : double
            The total weight of all samples.
        samples : array-like, dtype=SIZE_t
            A mask on the samples, showing which ones we want to use
        """
        pass


cdef class TwoMeans(UnsupervisedCriterion):
    r"""Two means split impurity.

    The two means split finds the cutpoint that minimizes the one-dimensional
    2-means objective, which is finding the cutoff point where the total variance
    from cluster 1 and cluster 2 are minimal. 

    The mathematical optimization problem is to find the cutoff index ``s``,
    which is called 'pos' in scikit-learn.

        \min_s \sum_{i=1}^s (x_i - \hat{\mu}_1)^2 + \sum_{i=s+1}^N (x_i - \hat{\mu}_2)^2

    where x is a N-dimensional feature vector, N is the number of samples and the \mu
    terms are the estimated means of each cluster 1 and 2.
    """

    def __cinit__(self, const DTYPE_t[:] X):
        """Initialize attributes for this criterion.

        Parameters
        ----------
        X : array-like, dtype=DTYPE_t
            The dataset stored as a buffer for memory efficiency of shape
            (n_samples,).
        """
        self.start = 0
        self.pos = 0
        self.end = 0

        self.n_samples = 0
        self.n_node_samples = 0
        self.weighted_n_node_samples = 0.0
        self.weighted_n_left = 0.0
        self.weighted_n_right = 0.0

        cdef SIZE_t k = 0
        cdef SIZE_t max_n_classes = 0

    cdef int init(
        self,
        const DTYPE_t[:, :] X,
        const DOUBLE_t[:] sample_weight,
        double weighted_n_samples,
        const SIZE_t[:] sample_indices
    ) nogil except -1:
        """Initialize the criterion.

        This initializes the criterion at node samples[start:end] and children
        samples[start:start] and samples[start:end].

        Returns -1 in case of failure to allocate memory (and raise MemoryError)
        or 0 otherwise.

        Parameters
        ----------
        X : array-like, dtype=DOUBLE_t
            The target stored as a buffer for memory efficiency. Note that
            this is not used, but simply passed as a convenience function.
        sample_weight : array-like, dtype=DOUBLE_t
            The weight of each sample (i.e. row of X).
        weighted_n_samples : double
            The total weight of all samples.
        samples : array-like, dtype=SIZE_t
            A mask on the samples, showing which ones we want to use
        """
        self.X = X
        self.sample_weight = sample_weight
        self.weighted_n_samples = weighted_n_samples
        self.sample_indices = sample_indices
        
    cdef int reset(self) nogil except -1:
        """Reset the criterion at pos=start.

        Returns -1 in case of failure to allocate memory (and raise MemoryError)
        or 0 otherwise.
        """
        self.pos = self.start

        self.weighted_n_left = 0.0
        self.weighted_n_right = self.weighted_n_node_samples
        cdef SIZE_t k

        for k in range(self.n_outputs):
            memset(&self.sum_left[k, 0], 0, self.n_classes[k] * sizeof(double))
            memcpy(&self.sum_right[k, 0], &self.sum_total[k, 0], self.n_classes[k] * sizeof(double))
        return 0

    cdef int reverse_reset(self) nogil except -1:
        """Reset the criterion at pos=end.

        Returns -1 in case of failure to allocate memory (and raise MemoryError)
        or 0 otherwise.
        """
        self.pos = self.end

        self.weighted_n_left = self.weighted_n_node_samples
        self.weighted_n_right = 0.0
        cdef SIZE_t k

        for k in range(self.n_outputs):
            memset(&self.sum_right[k, 0], 0, self.n_classes[k] * sizeof(double))
            memcpy(&self.sum_left[k, 0],  &self.sum_total[k, 0], self.n_classes[k] * sizeof(double))
        return 0

    cdef int update(self, SIZE_t new_pos) nogil except -1:
        """Updated statistics by moving samples[pos:new_pos] to the left child.

        Returns -1 in case of failure to allocate memory (and raise MemoryError)
        or 0 otherwise.

        Parameters
        ----------
        new_pos : SIZE_t
            The new ending position for which to move samples from the right
            child to the left child.
        """
        cdef SIZE_t pos = self.pos
        cdef SIZE_t end = self.end

        cdef const SIZE_t[:] sample_indices = self.sample_indices
        cdef const DOUBLE_t[:] sample_weight = self.sample_weight

        cdef SIZE_t i
        cdef SIZE_t p
        cdef SIZE_t k
        cdef SIZE_t c
        cdef DOUBLE_t w = 1.0

        # Update statistics up to new_pos
        #
        # Given that
        #   sum_left[x] +  sum_right[x] = sum_total[x]
        # and that sum_total is known, we are going to update
        # sum_left from the direction that require the least amount
        # of computations, i.e. from pos to new_pos or from end to new_po.
        if (new_pos - pos) <= (end - new_pos):
            for p in range(pos, new_pos):
                i = sample_indices[p]

                if sample_weight is not None:
                    w = sample_weight[i]

                for k in range(self.n_outputs):
                    self.sum_left[k, <SIZE_t> self.y[i, k]] += w

                self.weighted_n_left += w

        else:
            self.reverse_reset()

            for p in range(end - 1, new_pos - 1, -1):
                i = sample_indices[p]

                if sample_weight is not None:
                    w = sample_weight[i]

                for k in range(self.n_outputs):
                    self.sum_left[k, <SIZE_t> self.y[i, k]] -= w

                self.weighted_n_left -= w

        # Update right part statistics
        self.weighted_n_right = self.weighted_n_node_samples - self.weighted_n_left
        for k in range(self.n_outputs):
            for c in range(self.n_classes[k]):
                self.sum_right[k, c] = self.sum_total[k, c] - self.sum_left[k, c]

        self.pos = new_pos
        return 0

    cdef double node_impurity(self) nogil:
        """Evaluate the impurity of the current node.

        Evaluate the TwoMeans criterion as impurity of the current node,
        i.e. the impurity of sample_indices[start:end]. The smaller the impurity the
        better.
        """
        cdef SIZE_t pos = self.pos
        cdef SIZE_t end = self.end
        cdef const DTYPE_t[:, :] X = self.X

        cdef double impurity = 0.0
        cdef double mu_left #left mean
        cdef double mu_right #right mean
        cdef double left_c = 0.0 #left cluster
        cdef double right_c = 0.0 #right cluster
        cdef SIZE_t k
        cdef SIZE_t c

        mu_left = X[:pos].sum()
        mu_right = X[pos:end].sum()

        for k in range(pos):
            left_s += (X[k] - mu_left)**2

        for c in range(pos,end):
            right_s += (X[c] - mu_right)**2

        impurity = left_s + right_s
        impurity /= self.weighted_n_node_samples

        return impurity

    cdef void children_impurity(self, double* impurity_left,
                                double* impurity_right) nogil:
        # cdef double entropy_left = 0.0
        # cdef double entropy_right = 0.0
        # cdef double count_k
        # cdef SIZE_t k
        # cdef SIZE_t c

        # for k in range(self.n_outputs):
        #     for c in range(self.n_classes[k]):
        #         count_k = self.sum_left[k, c]
        #         if count_k > 0.0:
        #             count_k /= self.weighted_n_left
        #             entropy_left -= count_k * log(count_k)

        #         count_k = self.sum_right[k, c]
        #         if count_k > 0.0:
        #             count_k /= self.weighted_n_right
        #             entropy_right -= count_k * log(count_k)

        # impurity_left[0] = entropy_left / self.n_outputs
        # impurity_right[0] = entropy_right / self.n_outputs
        
        # use left_sum and right_sum to calculate impurity?
        # or should this method take two separate Xs making up
        # left and right child nodes?
        pass

    cdef void node_value(self, double* dest) nogil:
        r"""Compute the node value of samples[start:end] and save it into dest.

        Node-Wise Feature Generation
        URerF doesn't choose split points in the original feature space
        It follows the random projection framework

        \tilde{X}= A^T X'

        where, A is p x d matrix distributed as f_A, where f_A is the 
        projection distribution and d is the dimensionality of the 
        projected space. A is generated by randomly sampling from 
        {-1,+1} lpd times, then distributing these values uniformly 
        at random in A. l parameter is used to control the sparsity of A
        and is set to 1/20.

        Each of the d rows \tilde{X}[i; :], i \in {1,2,...d} is then 
        inspected for the best split point. The optimal split point and 
        splitting dimension are chosen according to which point/dimension
        pair minimizes the splitting criteria described in the following 
        section

        Parameters
        ----------
        dest : double pointer
            The memory address which we will save the node value into.
        """
        cdef SIZE_t k

        for k in range(self.n_outputs):
            memcpy(dest, &self.sum_total[k, 0], self.n_classes[k] * sizeof(double))
            dest += self.max_n_classes

    cdef void set_sample_pointers(
        self,
        SIZE_t start,
        SIZE_t end
    ) nogil:
        """Set sample pointers in the criterion."""
        self.n_node_samples = end - start
        self.start = start
        self.end = end

        self.weighted_n_node_samples = 0.0

        cdef SIZE_t i
        cdef SIZE_t p
        cdef SIZE_t k
        cdef SIZE_t c
        cdef DOUBLE_t w = 1.0

        for p in range(start, end):
            i = self.sample_indices[p]

            # w is originally set to be 1.0, meaning that if no sample weights
            # are given, the default weight of each sample is 1.0.
            if self.sample_weight is not None:
                w = self.sample_weight[i]

            self.weighted_n_node_samples += w

        # Reset to pos=start
        self.reset()