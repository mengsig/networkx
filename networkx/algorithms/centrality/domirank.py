"""DomiRank Centrality: By Marcus Engsig (@mengsig)"""

import networkx as nx
from networkx.utils import not_implemented_for

__all__ = ["domirank"]


@not_implemented_for("multigraph")
@nx._dispatchable(edge_attrs="weight")
def domirank(
    G, analytical=False, sigma=0.95, dt=0.1, epsilon=1e-5, max_iter=1000, check_step=10
):
    r"""Compute the DomiRank centrality for the graph `G`.

    DomiRank centrality computes the centrality for a node by adding
    1 minus the centrality of its neighborhood. This essentially finds the
    dominance of a node in its neighborhood, where the parameter $\sigma$ determines
    the amount of competition in the system. The competition parameter $\sigma$
    tunes the balance of DomiRank centrality's integration of local and global topological
    information, to find nodes that are either locally or globally Dominant. It is
    important to note that for the iterative formulation of DomiRank (as seen below),
    the competition parameter is bounded: $\sigma \in [0,\frac{1}{-lambda_N}].
    DomiRank is defined as the stationary solution to the dynamical system:

    .. math::

        \frac{d \Gamma_i(t)}{dt} = \sigma (d_i - \sum_j A_{ij} \Gamma_j(t)) - \Gamma_i(t),

    where $A$ is the adjacency matrix and $d_i$ is the degree of node $i$.
    Note that the definition presented here is valid for unweighted, weighted,
    directed, and undirected networks, so in the more general case,
    a non-zero entry of the adjacency matrix $A_{ij}=w_{ij}$
    represents the existence of a link from node $i$ to node $j$
    with a weight $w_{ij}$. In general, one will notice that important
    nodes identified by DomiRank will be connected to a lot of other
    unimportant nodes. However, other positionally important nodes
    can also be dominanted by joint-dominance of nodes, that work together
    in order to dominate another positionally important node. This centrality
    has a lot of interesting emergent phenomena, so it is recommend to
    see [1] for more information. That being said, DomiRank can also be
    expressed in its analytical form, where the competition can now be
    supercharged - i.e. $\sigma \in [0,\inf]$. The analytical equation
    takes the form:

    .. math::

        \boldsymbol{\Gamma} = \sigma (\sigma A + I_{N\times N})^{-1}  A  \boldsymbol{1}_{N\times 1},

    where $I$ is the identity matrix. This analytical equation can be solved
    as a linear system.

    Interestingly, DomiRank tends to have only positive values for
    relatively low competition levels (small $\sigma$), however, as
    the competition levels increase, negative values might emerge.
    Nodes with negative dominance represent completely submissive nodes,
    which instead of fighting for their resources/dominance, directly
    give up these resources to their neighborhood.

    Finally, it is not required that the network is weakly or strongly
    connected, and can be applied to networks with many components.

    Parameters
    ----------
    G : graph
      A networkx graph.

    analytical: bool, optinal (default=False)
      Boolean representing if the analytical or iterative formulation
      for computing DomiRank should be used.

    sigma: float, optional (default=0.95)
     The level of competition for DomiRank.

    dt: float, optional (default=0.1)
     The step size for the Newton iteration.

    epsilon: float, optional (default=1e-5)
     The relative stopping criterion for convergence.

    max_iter: integer, optional (default=50)
      Maximum number of Newton iterations allowed.

    check_step: integer, optional (default=10)
     The number of steps between checking whether or
     not DomiRank has converged/diverged.
     Note, this paramter must satisfy check_step > 2.


    Returns
    -------
    nodes : dictionary
       Dictionary of nodes with DomiRank centrality as the value.

    sigma : float
       The input $\sigma \in [0,1]$ normalized by the smallest eigenvalue

    converged: boolean
       A boolean representing whether or not the method did not diverge.

    Examples
    --------
    >>> G = nx.path_graph(5)
    >>> centrality, sigma, converged = nx.domirank(G)
    >>> print([f"{node} {centrality[node]:0.2f}" for node in centrality])
    ['0 -0.54', '1 1.98', '2 -1.08', '3 1.98', '4 -0.54']

    Raises
    ------
    NetworkXPointlessConcept
        If the graph G is the null graph.

    NetworkXError
        If the input for G is not a network.graph.classes.Graph object

    Warning
        If one is supercharging the competition parameter for the
        analytical solution.
    Warning
        If one is using the analytical solution for a large system
        - i.e. len(G) > 5000, as the algorithm will be slow.

    See Also
    --------
    :func:`scipy.sparse.linalg.solve`
    :func:`~networkx.algorithms.link_analysis.pagerank_alg.pagerank`
    :func:`~networkx.algorithms.link_analysis.hits_alg.hits`

    References
    ----------
    .. [1] Engsig, M., Tejedor, A., Moreno, Y. et al.
    "DomiRank Centrality reveals structural fragility of complex networks via node dominance."
    Nat Commun 15, 56 (2024). https://doi.org/10.1038/s41467-023-44257-0
    """
    import numpy as np
    import scipy as sp

    if (
        type(G) == nx.classes.graph.Graph or type(G) == nx.classes.digraph.DiGraph
    ):  # check if it is a networkx Graph
        if len(G) == 0:
            raise nx.NetworkXPointlessConcept(
                "cannot compute centrality for the null graph"
            )
        GAdj = nx.to_scipy_sparse_array(G)  # convert to scipy sparse csr array
    else:
        raise nx.NetworkXError(
            "can only compute the centrality for nx.classes.graph.Graph object"
        )
    # Here we renormalize sigma with the smallest eigenvalue (most negative eigenvalue) by calling the "hidden" function _find_smallest_eigenvalue()
    # Note, this function always uses the recursive definition
    if analytical == False:
        # If the recursive formulation is used, the sigma has to be bounded (competition parameter).
        if sigma < 0:
            raise nx.NetworkXUnfeasible(
                "the competition parameter sigma must be positive and bounded such that sigma: [0,1]"
            )
        if sigma > 1:
            raise nx.NetworkXUnfeasible(
                "supercharging the competition parameter (sigma > 1) requires the <analytical = True> flag"
            )
        sigma = np.abs(
            sigma
            / _find_smallest_eigenvalue(
                GAdj,
                maxDepth=int(max_iter / 5),
                dt=dt,
                epsilon=epsilon,
                max_iter=max_iter,
                check_step=check_step,
            )
        )
        # store this to prevent more redundant calculations in the future
        pGAdj = sigma * GAdj.astype(np.float32)
        # initalize a proportionally (to system size) small non-zero uniform vector
        Psi = np.ones(pGAdj.shape[0]).astype(np.float32) / pGAdj.shape[0]
        # initialize a zero array to store values (yes, this could be done with a smaller array with some smart indexing, but this is not computationally or memory heavy)
        maxVals = np.zeros(int(max_iter / check_step)).astype(np.float32)
        # ensure dt is a float
        dt = np.float32(dt)
        # start a counter
        j = 0
        # set up a boundary condition for stopping divergence
        boundary = epsilon * pGAdj.shape[0] * dt
        for i in range(max_iter):
            # DomiRank recursive definition
            tempVal = ((pGAdj @ (1 - Psi)) - Psi) * dt
            # Newton iteration addition step
            Psi += tempVal.real
            # Here we do the checking to see if we are diverging
            if i % check_step == 0:
                if np.abs(tempVal).sum() < boundary:
                    break
                maxVals[j] = tempVal.max()
                if i == 0:
                    initialChange = maxVals[j]
                if j > 0:
                    if maxVals[j] > maxVals[j - 1] and maxVals[j - 1] > maxVals[j - 2]:
                        # If we are diverging, return the current step, but, with the argument that you have diverged.
                        Psi = dict(zip(G, (Psi).tolist()))
                        return Psi, sigma, False
                j += 1
        Psi = dict(zip(G, (Psi).tolist()))
        return Psi, sigma, True
    else:
        import warnings

        # Here we create a warning (I couldn't find a networkxwarning, only exceptions and erros), that suggests to use the iterative formulation of DomiRank rather than the analytical form.
        if GAdj.shape[0] > 5000:
            warnings.warn(
                "The system is large!!! Consider using <analytical = False> function argument for reduced computational time cost."
            )
        # Here we create another warning for sigma being supercharged
        if sigma > 1:
            warnings.warn(
                "You are supercharging the competition in the system by having sigma > 1, which is only permitted for the analytical solution!"
            )
        if sigma < 0:
            raise nx.NetworkXUnfeasible(
                "the competition parameter sigma must be positive - sigma > 0."
            )
        sigma = np.abs(
            sigma
            / _find_smallest_eigenvalue(
                GAdj,
                maxDepth=int(max_iter / 5),
                dt=dt,
                epsilon=epsilon,
                max_iter=max_iter,
                check_step=check_step,
            )
        )
        Psi = sp.sparse.linalg.spsolve(
            sigma * GAdj + sp.sparse.identity(GAdj.shape[0]), sigma * GAdj.sum(axis=-1)
        )
        Psi = dict(zip(G, (Psi).tolist()))
        return Psi, sigma, True


##### THE FUNCTIONS HEREUNDER SHOULD BE HIDDEN FUNCTIONS #####
def _find_smallest_eigenvalue(
    G,
    minVal=0,
    maxVal=1,
    maxDepth=100,
    dt=0.1,
    epsilon=1e-5,
    max_iter=100,
    check_step=10,
):
    """
    This function is simply used to find the smallest eigenvalue, by seeing when the DomiRank algorithm diverges. It uses
    a kind of binary search algorithm, however, with a bias to larger eigenvalues, as finding divergence is faster than
    ensuring convergence.
    This function outputs the smallest eigenvalue - i.e. most negative eigenvalue.
    """
    import numpy
    import scipy

    x = (minVal + maxVal) / G.sum(axis=-1).max()
    minValStored = 0
    for i in range(maxDepth):
        if maxVal - minVal < epsilon:
            break
        if _domirank(
            G, sigma=x, dt=dt, epsilon=epsilon, max_iter=max_iter, check_step=check_step
        ):
            minVal = x
            x = (minVal + maxVal) / 2
            minValStored = minVal
        else:
            maxVal = (x + maxVal) / 2
            x = (minVal + maxVal) / 2
    finalVal = (maxVal + minVal) / 2
    return -1 / finalVal


def _domirank(G, sigma=0, dt=0.1, epsilon=1e-5, max_iter=1000, check_step=10):
    """
    Is used to find the smallest eigenvalue - i.e. called in the _find_smallest_eigenvalue() function.
    It only outputs a boolean.
    """
    import numpy as np
    import scipy as sp

    pGAdj = sigma * G.astype(np.float32)
    Psi = np.ones(pGAdj.shape[0]).astype(np.float32) / pGAdj.shape[0]
    maxVals = np.zeros(int(max_iter / check_step)).astype(np.float32)
    dt = np.float32(dt)
    j = 0
    boundary = epsilon * pGAdj.shape[0] * dt
    for i in range(max_iter):
        tempVal = ((pGAdj @ (1 - Psi)) - Psi) * dt
        Psi += tempVal.real
        if i % check_step == 0:
            if np.abs(tempVal).sum() < boundary:
                break
            maxVals[j] = tempVal.max()
            if i == 0:
                initialChange = maxVals[j]
            if j > 0:
                if maxVals[j] > maxVals[j - 1] and maxVals[j - 1] > maxVals[j - 2]:
                    return False
            j += 1
    return True
