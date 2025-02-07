"""Underlying simulator for the YYG/C19Pro SEIR model.

Learn more at: https://github.com/youyanggu/yyg-seir-simulator. Developed by Youyang Gu.
"""

import datetime

import numpy as np

from fixed_params import *


def get_daily_imports(region_model, i):
    """Returns the number of new daily imported cases based on day index i (out of N days).

    - beginning_days_flat is how many days at the beginning we maintain a constant import.
    - end_days_offset is the number of days from the end of the projections
        before we get 0 new imports.
    - The number of daily imports is initially region_model.daily_imports, and
        decreases linearly until day N-end_days_offset.
    """

    N = region_model.N
    assert i < N, 'day index must be less than total days'

    if hasattr(region_model, 'beginning_days_flat'):
        beginning_days_flat = region_model.beginning_days_flat
    else:
        beginning_days_flat = 10
    assert beginning_days_flat >= 0

    if hasattr(region_model, 'end_days_offset'):
        end_days_offset = region_model.end_days_offset
    else:
        end_days_offset = int(N - min(N, DAYS_WITH_IMPORTS))
    assert beginning_days_flat + end_days_offset <= N
    n_ = N - beginning_days_flat - end_days_offset + 1

    daily_imports = region_model.daily_imports * \
        (1 - min(1, max(0, (i-beginning_days_flat+1)) / n_))

    if region_model.country_str not in ['China', 'South Korea', 'Australia'] and not \
            hasattr(region_model, 'end_days_offset'):
        # we want to maintain ~10 min daily imports a day
        daily_imports = max(daily_imports, min(10, 0.1 * region_model.daily_imports))

    return daily_imports


# Added to compute a sigmoid function
def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def inverse_sigmoid_decay(t, k=1, t_0=50, start=0.5, end=0.25):
    range_width = start - end
    return end + range_width * (1 - 1 / (1 + np.exp(-k * (t - t_0))))

def run(region_model):
    """Given a RegionModel object, runs the SEIR simulation."""
    dates = np.array([region_model.first_date + datetime.timedelta(days=i) \
        for i in range(region_model.N)])
    infections = np.array([0.] * region_model.N)
    hospitalizations = np.zeros(region_model.N) * np.nan
    deaths = np.array([0.] * region_model.N)
    reported_deaths = np.array([0.] * region_model.N)
    mortaility_rates = np.array([region_model.MORTALITY_RATE] * region_model.N)

    assert infections.dtype == hospitalizations.dtype == \
        deaths.dtype == reported_deaths.dtype == mortaility_rates.dtype == np.float64

    """
    We compute a normalized version of the infections and deaths probability distribution.
    We invert the infections and deaths norm to simplify the convolutions we will take later.
        Aka the beginning of the array is the farther days out in the convolution.
    """
    deaths_norm = DEATHS_DAYS_ARR[::-1] / DEATHS_DAYS_ARR.sum()
    infections_norm = INFECTIOUS_DAYS_ARR[::-1] / INFECTIOUS_DAYS_ARR.sum()

    infections_mask_norm = INFECTIOUS_DAYS_ARR[::-1] / INFECTIOUS_DAYS_ARR.sum()
    if hasattr(region_model, 'quarantine_fraction'):
        # reduce infections in the latter end of the infectious period, based on reduction_idx
        infections_norm[:region_model.reduction_idx] = \
            infections_norm[:region_model.reduction_idx] * (1 - region_model.quarantine_fraction)
        infections_norm[region_model.reduction_idx] = \
            (infections_norm[region_model.reduction_idx] * 0.5) + \
            (infections_norm[region_model.reduction_idx] * 0.5 * \
                (1 - region_model.quarantine_fraction))

    infections_mask_mandate_norm = []

    # Modify infection distribution based on mask mandate
    if hasattr(region_model, 'mask_fraction'):
        # sigmoid function on mask percent
        num_mandate_days = (region_model.mask_end_date_ind - region_model.mask_start_date_ind) + 1
        t = np.linspace(0,100, num_mandate_days)
        mask_fracs = inverse_sigmoid_decay(t, k=0.1, t_0=50, start=region_model.mask_fraction, end=region_model.mask_fraction*region_model.mask_fall_off)

        for i in range(num_mandate_days):
            tmp = INFECTIOUS_DAYS_ARR[::-1] / INFECTIOUS_DAYS_ARR.sum()
            tmp[:region_model.mask_reduction_idx] = tmp[:region_model.mask_reduction_idx] * (1 - mask_fracs[i])
            tmp[region_model.mask_reduction_idx] = (tmp[region_model.mask_reduction_idx] * 0.5) + (tmp[region_model.mask_reduction_idx] * 0.5 * (1 - mask_fracs[i]))
            infections_mask_mandate_norm.append(tmp)

    # the greater the immunity mult, the greater the effect of immunity
    assert 0 <= region_model.immunity_mult <= 2, region_model.immunity_mult

    

    ########################################
    # Compute infections
    ########################################
    effective_r_arr = []
    for i in range(region_model.N):
        if i < INCUBATION_DAYS+len(infections_norm):
            # initialize infections
            infections[i] = region_model.daily_imports
            effective_r_arr.append(region_model.R_0_ARR[i])
            continue

        # assume 50% of population lose immunity after 6 months
        infected_thus_far = infections[:max(0, i-180)].sum() * 0.5 + infections[max(0, i-180):i-1].sum()
        perc_population_infected_thus_far = \
            min(1., infected_thus_far / region_model.population)
        assert 0 <= perc_population_infected_thus_far <= 1, perc_population_infected_thus_far

        r_immunity_perc = (1. - perc_population_infected_thus_far)**region_model.immunity_mult
        effective_r = region_model.R_0_ARR[i] * r_immunity_perc
        # we apply a convolution on the infections norm array
        # Check if we are during the mask mandate

        if hasattr(region_model, 'mask_fraction') and i >= region_model.mask_start_date_ind and i <= region_model.mask_end_date_ind:
            curr_mask_mandate_ind = i - region_model.mask_start_date_ind
            s = (infections[i-INCUBATION_DAYS-len(infections_mask_mandate_norm[curr_mask_mandate_ind])+1:i-INCUBATION_DAYS+1] * \
                infections_mask_mandate_norm[curr_mask_mandate_ind]).sum() * effective_r
        else:
            s = (infections[i-INCUBATION_DAYS-len(infections_norm)+1:i-INCUBATION_DAYS+1] * \
                infections_norm).sum() * effective_r
    
        infections[i] = s + get_daily_imports(region_model, i)
        effective_r_arr.append(effective_r)

    region_model.perc_population_infected_final = perc_population_infected_thus_far
    assert len(region_model.R_0_ARR) == len(effective_r_arr) == region_model.N
    region_model.effective_r_arr = effective_r_arr

    ########################################
    # Compute hospitalizations
    ########################################
    if region_model.compute_hospitalizations:
        """
        Simple estimation of hospitalizations by taking the sum of a
            window of n days of new infections * hospitalization rate
        Note: this represents hospital beds used on on day _i, not new hospitalizations
        """
        for _i in range(region_model.N):
            start_idx = max(0, _i-DAYS_UNTIL_HOSPITALIZATION-DAYS_IN_HOSPITAL)
            end_idx = max(0, _i-DAYS_UNTIL_HOSPITALIZATION)
            hospitalizations[_i] = int(HOSPITALIZATION_RATE * infections[start_idx:end_idx].sum())

    ########################################
    # Compute true deaths
    ########################################
    assert len(deaths_norm) % 2 == 1, 'deaths arr must be odd length'
    deaths_offset = len(deaths_norm) // 2
    for _i in range(-deaths_offset, region_model.N-DAYS_BEFORE_DEATH):
        # we apply a convolution on the deaths norm array
        infections_subject_to_death = (infections[max(0, _i-deaths_offset):_i+deaths_offset+1] * \
            deaths_norm[:min(len(deaths_norm), deaths_offset+_i+1)]).sum()
        true_deaths = infections_subject_to_death * region_model.ifr_arr[_i + DAYS_BEFORE_DEATH]
        deaths[_i + DAYS_BEFORE_DEATH] = true_deaths

    ########################################
    # Compute reported deaths
    ########################################
    death_reporting_lag_arr_norm = region_model.get_reporting_delay_distribution()
    assert abs(death_reporting_lag_arr_norm.sum() - 1) < 1e-9, death_reporting_lag_arr_norm
    for i in range(region_model.N):
        """
        This section converts true deaths to reported deaths.

        We first assume that a small minority of deaths are undetected, and remove those.
        We then assume there is a reporting delay that is exponentially decreasing over time.
            The probability density function of the delay is encoded in death_reporting_lag_arr.
            In reality, reporting delays vary from region to region.
        """
        detected_deaths = deaths[i] * (1 - region_model.undetected_deaths_ratio_arr[i])
        max_idx = min(len(death_reporting_lag_arr_norm), len(deaths) - i)
        reported_deaths[i:i+max_idx] += \
            (death_reporting_lag_arr_norm * detected_deaths)[:max_idx]

    return dates, infections, hospitalizations, reported_deaths

