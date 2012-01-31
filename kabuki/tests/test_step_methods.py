import unittest
import kabuki
import numpy as np
import pymc as pm
import math
import scipy as sc
from pprint import pprint
from numpy.random import randn
from numpy import array, sqrt
from nose import SkipTest

class TestStepMethods(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(TestStepMethods, self).__init__(*args, **kwargs)
        self.uniform_lb = 1e-10
        self.uniform_ub = 1e10

    def runTest(self):
        return


    def assert_results(self, node, true_value, true_mean, true_std=None,
                       mean_tol=0.1, std_tol=0.2):
        """check if the sampler output agree with the analytical meand and
        analytical std
        Input:
            Node - the node to check
            true_value - the true value of the node
            true_mean - the true mean
            true_std - the std of the distribution (None if it's unknown)
            mean_tol - the tolerance to use when checking the difference between
                the true_mean and the sampled mean
            std_tol - same as mean_tol but for checking the std
        """

        pprint(node.stats())
        lb = node.stats()['quantiles'][2.5]
        ub = node.stats()['quantiles'][97.5]
        if not (lb <  true_value < ub):
            print "Warnnig!!!!, sigma was not found in the credible set"


        print "true value:     ", true_value
        print "sampled median: ", node.stats()['quantiles'][50]
        print "sampled mean:   ", node.stats()['mean']
        print "true mean:      ", true_mean
        if true_std is not None:
            print "true std:       ", true_std
            print "sampled std:    ", node.stats()['standard deviation']

        np.testing.assert_allclose(node.stats()['mean'], true_mean, rtol=mean_tol)
        if true_std is not None:
            np.testing.assert_allclose(node.stats()['standard deviation'], true_std, rtol=std_tol)


    def normal_normal(self, add_shift, sigma_0, sigma_beta, sigma_y, true_mu,
                     n_subjs, avg_samples, seed, use_metropolis):
        """check the normal_normal configuration
        Model:
        x ~ N(mu_0, sigma_0**-2)
        y ~ N(x + b, sigma_y**-2)
        only mu is Stochastic

        b is constant in the model. it is generated from N(o,sigma_b**-2)
        y is generated from N(true_mu + b, sigma_y**-2)
            add_shift - whether to add some

        n_subjs - number of b
        avg_samples - the average samples per subject

        """

        np.random.seed(seed)

        #create nodes
        tau_0 = sigma_0**-2
        mu_0 = 0.
        nodes, size, x_values = \
        self.create_nodes_for_normal_normal(add_shift, tau_0, mu_0, sigma_beta,
                                       sigma_y, true_mu, n_subjs, avg_samples)
        mu = nodes['mu']

        #sample
        mm = pm.MCMC(nodes)
        if use_metropolis:
            mm.sample(20000,5000)
        else:
            mm.use_step_method(kabuki.steps.kNormalNormal,mu)#, b=b)
            mm.sample(10000)

        #calc the new distrbution
        total_n = sum(size)
        tau = sigma_y**-2
        sum_obs = sum([sum(x.value.flatten()) for x in mm.observed_stochastics])
        if add_shift:
            tmp = sum(array(size)* x_values)
        else:
            tmp = 0

        tau_prime = tau_0 + total_n*tau
        mu_prime = (tau*(sum_obs - tmp) + mu_0*tau_0)/tau_prime
        true_std = 1./np.sqrt(tau_prime)

        self.assert_results(mu, true_mu, mu_prime, true_std, mean_tol=0.1, std_tol=0.1)

        return mm, mu_prime, true_std

    def create_nodes_for_normal_normal(self, add_shift, tau_0, mu_0, sigma_beta,
                                       sigma_y, true_mu, n_subjs, avg_samples):
        """ create the normal normal nodes"""

        mu = pm.Normal('mu',mu_0,tau_0)
        nodes = {'mu': mu}
        size = [None]*n_subjs
        x_values = [None]*n_subjs
        if add_shift:
            b = []
        else:
            b = None
        for i in range(n_subjs):
            size[i] = int(max(1, avg_samples + randn()*10))
            if add_shift:
                x_values[i] = randn()*sigma_beta
                value = randn(size[i]) * sigma_y + true_mu + x_values[i]
                x = pm.Lambda('x%d' % i, lambda x=x_values[i]:x)
#                x = pm.Uniform('x%d' % i, x_values[i], x_values[i]+1e-6)
                y = pm.Normal('y%d' % i,mu+x, sigma_y**-2, value=value,observed=True)
                nodes['x%d' % i] = x
                b.append(x)
            else:
                value = randn(size[i]) * sigma_y + true_mu
                y = pm.Normal('y%d' % i,mu, sigma_y**-2, value=value,observed=True)

            nodes['y%d' % i] = y

        return nodes, size, x_values


    def normal_normal_bundle(self, use_metropolis):
        """run normal_normal with different parameters"""
        self.normal_normal(add_shift=True, sigma_0=100., sigma_beta=2., sigma_y=1.5,
                         true_mu=-3., n_subjs=1, avg_samples=100, seed=1, use_metropolis=use_metropolis)
        self.normal_normal(add_shift=True, sigma_0=50., sigma_beta=3., sigma_y=2,
                         true_mu=-2., n_subjs=2, avg_samples=10, seed=2, use_metropolis=use_metropolis)
        self.normal_normal(add_shift=True, sigma_0=10., sigma_beta=1., sigma_y=2.5,
                         true_mu=-1., n_subjs=3, avg_samples=10, seed=3, use_metropolis=use_metropolis)
        self.normal_normal(add_shift=False, sigma_0=1., sigma_beta=0.5, sigma_y=0.5,
                         true_mu=-4., n_subjs=4, avg_samples=50, seed=4, use_metropolis=use_metropolis)
        self.normal_normal(add_shift=False, sigma_0=50., sigma_beta=0.3, sigma_y=1.5,
                         true_mu=-6., n_subjs=5, avg_samples=50, seed=5, use_metropolis=use_metropolis)
        self.normal_normal(add_shift=False, sigma_0=100., sigma_beta=0.75, sigma_y=2.5,
                         true_mu=100., n_subjs=6, avg_samples=30, seed=6, use_metropolis=use_metropolis)

    def test_normal_normal_solution(self):
        """test normal normal analytic solution"""
        self.normal_normal_bundle(use_metropolis=True)


    def test_kNormalNormal(self):
        """test normal_normal step method"""
        self.normal_normal_bundle(use_metropolis=False)


    def create_nodes_for_PriorNormalstd(self, n_subjs, sigma_0, mu_0, prior, **kwargs):
        """"create node for models with PriorNormalstd step method"""
        #create nodes
        if prior is pm.Uniform:
            sigma = pm.Uniform('sigma', self.uniform_lb, self.uniform_ub, value=1.)
        elif prior is kabuki.utils.HalfCauchy:
            sigma = kabuki.utils.HalfCauchy('sigma', **kwargs)

        x_values = [None]*n_subjs
        nodes = {'sigma': sigma}
        for i in range(n_subjs):
            x_values[i] = randn()*sigma_0 + mu_0
            x = pm.Normal('x%d' % i, mu_0, sigma**-2, value=x_values[i], observed=True)
            nodes['x%d' % i] = x
        return nodes, x_values


    def uniform_normalstd(self, sigma_0, mu_0, n_subjs, seed, use_metropolis):
        """test estimation of Normal distribution std with uniform prior
            sigma_0 - the value of the std noe
            mu_0 - the value of the mu node
            use_metropolis - should it use metropolis to evaluate the sampled mean
                instead of the UniformPriorNormalstd
        """

        np.random.seed(seed)

        nodes, x_values = self.create_nodes_for_PriorNormalstd(n_subjs, sigma_0, mu_0, prior=pm.Uniform)
        sigma = nodes['sigma']
        mm = pm.MCMC(nodes)

        if use_metropolis:
            mm.sample(20000,5000)
        else:
            mm.use_step_method(kabuki.steps.UniformPriorNormalstd, sigma)
            mm.sample(10000)



        #calc the new distrbution
        alpha = (n_subjs - 1) / 2.
        beta  = sum([(x - mu_0)**2 for x in x_values]) / 2.
        true_mean = math.gamma(alpha-0.5)/math.gamma(alpha)*np.sqrt(beta)
        anal_var = beta / (alpha - 1) - true_mean**2
        true_std = np.sqrt(anal_var)

        self.assert_results(sigma, sigma_0, true_mean, true_std)
        return mm


    def test_uniform_normalstd_numerical_solution(self):
        """test uniform_normalstd with Metropolis to evaluate the numerical solution of
        the mean and std"""
        self.uniform_normalstd(sigma_0=0.5, mu_0=0, n_subjs=8, seed=1, use_metropolis=True)
        self.uniform_normalstd(sigma_0=1.5, mu_0=-100, n_subjs=4, seed=2, use_metropolis=True)
        self.uniform_normalstd(sigma_0=2.5, mu_0=2, n_subjs=5, seed=3, use_metropolis=True)
        self.uniform_normalstd(sigma_0=3.5, mu_0=-4, n_subjs=7, seed=4, use_metropolis=True)
#        self.uniform_normalstd(sigma_0=4.5, mu_0=10, n_subjs=4, seed=5, use_metropolis=True)

    def test_UniformNormalstd_step_method(self):
        """test UniformPriorNormalstd step method"""
        self.uniform_normalstd(sigma_0=0.5, mu_0=0, n_subjs=8, seed=1, use_metropolis=False)
        self.uniform_normalstd(sigma_0=1.5, mu_0=-100, n_subjs=4, seed=2, use_metropolis=False)
        self.uniform_normalstd(sigma_0=2.5, mu_0=2, n_subjs=5, seed=3, use_metropolis=False)
        self.uniform_normalstd(sigma_0=3.5, mu_0=-4, n_subjs=7, seed=4, use_metropolis=False)
        self.uniform_normalstd(sigma_0=4.5, mu_0=10, n_subjs=4, seed=5, use_metropolis=False)


    def numerical_solution(self, defective_posterior, lb, ub):
        """numerical estimation of the mean and std from defective posterior
        defective_posterior <func> - the defective posterior
        lb - lower bound
        ub - upper bound
        """

        norm_factor = sc.integrate.quad(defective_posterior,lb,ub)[0]
        #function to compute moments
        moment = lambda x,n=1: defective_posterior(x) * (x**n) / norm_factor

        #computing mean and std
        true_mean = sc.integrate.quad(moment,lb, ub, args=(1))[0]
        m2 = sc.integrate.quad(moment,lb, ub, args=(2))[0]
        anal_var = m2 - true_mean**2
        true_std = np.sqrt(anal_var)
        return true_mean, true_std


    def half_cauchy_normal_std(self, sigma_0=1., mu_0=0., S=10, n_subjs=8, seed=1,
                            use_metropolis=False):
        """test estimation of Normal distribution std with halh Cauchy prior
            sigma_0 - the value of the std noe
            mu_0 - the value of the mu node
            S - the scale of the half Cauchy
            use_metropolis - should it use metropolis to evaluate the sampled mean
                instead of the UniformPriorNormalstd
        """


        #create model
        np.random.seed(seed)
        nodes, x_values = \
        self.create_nodes_for_PriorNormalstd(n_subjs, sigma_0, mu_0,
                                             prior=kabuki.utils.HalfCauchy,
                                             S=S, value=1)
        sigma = nodes['sigma']

        #sample
        mm = pm.MCMC(nodes)
        if use_metropolis:
            mm.sample(20000,5000)
        else:
            mm.use_step_method(kabuki.steps.HCauchyPriorNormalstd, sigma)
            mm.sample(10)

        #compute defective posterior
        beta = sum((array(x_values) - mu_0)**2)/2
        def defective_posterior(x, n=n_subjs, beta=beta, S=S):
           gammapdf = (x**2)**(-n/2.) * np.exp(-beta/(x**2))
           cauchy = S / (x**2 + S**2)
           return gammapdf * cauchy

        #check results
        true_mean, true_std = self.numerical_solution(defective_posterior, 0, np.inf)
        self.assert_results(sigma, sigma_0, true_mean, true_std)
        return mm

    def half_cauchy_bundle(self, use_metropolis):
        self.half_cauchy_normal_std(sigma_0=4.5, mu_0=0, n_subjs=8, seed=1, S=5,
                                    use_metropolis=use_metropolis)
        self.half_cauchy_normal_std(sigma_0=0.5, mu_0=-100, n_subjs=4, seed=2, S=20,
                                    use_metropolis=use_metropolis)
        self.half_cauchy_normal_std(sigma_0=5.5, mu_0=2, n_subjs=5, seed=3, S=3,
                                    use_metropolis=use_metropolis)
        self.half_cauchy_normal_std(sigma_0=1.5, mu_0=-4, n_subjs=7, seed=4, S=10,
                                    use_metropolis=use_metropolis)
        self.half_cauchy_normal_std(sigma_0=4.5, mu_0=10, n_subjs=4, seed=5, S=15,
                                    use_metropolis=use_metropolis)

    def test_half_cauchy_numerical_solution(self):
        """test half_cauchy_normal_std with Metropolis to evaluate the numerical solution of
        the mean and std"""
        self.half_cauchy_bundle(use_metropolis=True)

    def test_HCauchyNormalstd_step_method(self):
        """test HCauchy step method"""
        raise SkipTest("The HCauchy gibbs step method does not work.")
        self.half_cauchy_bundle(use_metropolis=False)
