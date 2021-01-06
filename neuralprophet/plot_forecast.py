import numpy as np
import pandas as pd
import logging
from neuralprophet.utils import set_y_as_percent
from neuralprophet.plot_model_parameters import plot_yearly, plot_weekly, plot_daily, plot_custom_season

log = logging.getLogger("NP.plotting")

try:
    from matplotlib import pyplot as plt
    from matplotlib.dates import (
        MonthLocator,
        num2date,
        AutoDateLocator,
        AutoDateFormatter,
    )
    from matplotlib.ticker import FuncFormatter

    from pandas.plotting import deregister_matplotlib_converters

    deregister_matplotlib_converters()
except ImportError:
    log.error("Importing matplotlib failed. Plotting will not work.")


def plot(
    fcst,
    quantiles=None,
    ax=None,
    xlabel="ds",
    ylabel="y",
    highlight_forecast=None,
    line_per_origin=False,
    figsize=(10, 6),
):
    """Plot the NeuralProphet forecast

    Args:
        fcst (pd.DataFrame):  output of m.predict.
        quantiles (list): the quantiles for which the forecasts are to be plotted
        ax (matplotlib axes):  on which to plot.
        xlabel (str): label name on X-axis
        ylabel (str): label name on Y-axis
        highlight_forecast (int): i-th step ahead forecast to highlight.
        line_per_origin (bool): print a line per forecast of one per forecast age
        figsize (tuple): width, height in inches.

    Returns:
        A matplotlib figure.
    """
    fcst = fcst.fillna(value=np.nan)
    if ax is None:
        fig = plt.figure(facecolor="w", figsize=figsize)
        ax = fig.add_subplot(111)
    else:
        fig = ax.get_figure()
    ds = fcst["ds"].dt.to_pydatetime()
    yhat_col_names = [col_name for col_name in fcst.columns if "yhat" in col_name]

    if highlight_forecast is None or line_per_origin:
        for i, name in enumerate(yhat_col_names):
            if quantiles is None:
                ax.plot(ds, fcst[name], ls="-", c="#0072B2", alpha=0.2 + 2.0 / (i + 2.5))
            else:
                ax.plot(ds, fcst[name], ls="-", c="#0072B2")

    if highlight_forecast is not None:
        if line_per_origin:
            num_forecast_steps = sum(fcst["yhat1"].notna())
            steps_from_last = num_forecast_steps - highlight_forecast
            for i in range(len(yhat_col_names)):
                x = ds[-(1 + i + steps_from_last)]
                y = fcst["yhat{}".format(i + 1)].values[-(1 + i + steps_from_last)]
                ax.plot(x, y, "bx")
        else:
            if quantiles is not None:
                for quantile in quantiles:
                    ax.plot(ds, fcst["yhat{} {}%".format(highlight_forecast, quantile * 100)], ls="-", c="b")
                    ax.plot(ds, fcst["yhat{} {}%".format(highlight_forecast, quantile * 100)], "bx")
                ax.fill_between(
                    ds,
                    fcst["yhat{} {}%".format(highlight_forecast, quantiles[0] * 100)],
                    fcst["yhat{} {}%".format(highlight_forecast, quantiles[-1] * 100)],
                    color="#0072B2",
                    alpha=0.2,
                )
            else:
                ax.plot(ds, fcst["yhat{}".format(highlight_forecast)], ls="-", c="b")
                ax.plot(ds, fcst["yhat{}".format(highlight_forecast)], "bx")

    ax.plot(ds, fcst["y"], "k.")

    # Specify formatting to workaround matplotlib issue #12925
    locator = AutoDateLocator(interval_multiples=False)
    formatter = AutoDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    ax.grid(True, which="major", c="gray", ls="-", lw=1, alpha=0.2)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    return fig


def plot_components(
    m, fcst, quantile=None, forecast_in_focus=None, one_period_per_season=True, residuals=False, figsize=None
):
    """Plot the NeuralProphet forecast components.

    Args:
        m (NeuralProphet): fitted model.
        fcst (pd.DataFrame):  output of m.predict.
        quantile (float): the quantile for which the forecast components are to be plotted
        forecast_in_focus (int): n-th step ahead forecast AR-coefficients to plot
        one_period_per_season (bool): plot one period per season
            instead of the true seasonal components of the forecast.
        figsize (tuple): width, height in inches.
                None (default):  automatic (10, 3 * npanel)

    Returns:
        A matplotlib figure.
    """
    log.debug("Plotting forecast components".format(fcst.head().to_string()))
    fcst = fcst.fillna(value=np.nan)

    # Identify components to be plotted
    # as dict, minimum: {plot_name, comp_name}
    components = []

    if quantile is not None:
        name_suffix = " " + str(quantile * 100) + "%"
    else:
        name_suffix = ""

    # Plot  trend
    components.append({"plot_name": "Trend " + name_suffix, "comp_name": "trend"})

    # Plot  seasonalities, if present
    if m.model.config_season is not None:
        for name in m.model.config_season.periods:
            components.append(
                {
                    "plot_name": "{} seasonality {}".format(name, name_suffix),
                    "comp_name": name,
                }
            )
    # AR
    if m.model.n_lags > 0:
        if forecast_in_focus is None:
            components.append(
                {
                    "plot_name": "Auto-Regression " + name_suffix,
                    "comp_name": "ar",
                    "num_overplot": m.n_forecasts,
                    "bar": True,
                }
            )
        else:
            components.append(
                {
                    "plot_name": "AR ({})-ahead {}".format(forecast_in_focus, name_suffix),
                    "comp_name": "ar{}".format(forecast_in_focus),
                }
            )
            # 'add_x': True})

    # Add Covariates
    if m.model.config_covar is not None:
        for name in m.model.config_covar.keys():
            if forecast_in_focus is None:
                components.append(
                    {
                        "plot_name": 'Lagged Regressor "{}" {}'.format(name, name_suffix),
                        "comp_name": "lagged_regressor_{}".format(name),
                        "num_overplot": m.n_forecasts,
                        "bar": True,
                    }
                )
            else:
                components.append(
                    {
                        "plot_name": 'Lagged Regressor "{}" ({})-ahead {}'.format(name, forecast_in_focus, name_suffix),
                        "comp_name": "lagged_regressor_{}{}".format(name, forecast_in_focus),
                    }
                )
                # 'add_x': True})
    # Add Events
    if "events_additive" in fcst.columns:
        components.append(
            {
                "plot_name": "Additive Events " + name_suffix,
                "comp_name": "events_additive",
            }
        )
    if "events_multiplicative" in fcst.columns:
        components.append(
            {
                "plot_name": "Multiplicative Events " + name_suffix,
                "comp_name": "events_multiplicative",
                "multiplicative": True,
            }
        )

    # Add Regressors
    if "future_regressors_additive" in fcst.columns:
        components.append(
            {
                "plot_name": "Additive Future Regressors " + name_suffix,
                "comp_name": "future_regressors_additive",
            }
        )
    if "future_regressors_multiplicative" in fcst.columns:
        components.append(
            {
                "plot_name": "Multiplicative Future Regressors " + name_suffix,
                "comp_name": "future_regressors_multiplicative",
                "multiplicative": True,
            }
        )
    if residuals:
        if forecast_in_focus is None and m.n_forecasts > 1:
            if fcst["residual1"].count() > 0:
                components.append(
                    {
                        "plot_name": "Residuals " + name_suffix,
                        "comp_name": "residual",
                        "num_overplot": m.n_forecasts,
                        "bar": True,
                    }
                )
        else:
            ahead = 1 if forecast_in_focus is None else forecast_in_focus
            if fcst["residual{}".format(ahead)].count() > 0:
                components.append(
                    {
                        "plot_name": "Residuals ({})-ahead {}".format(ahead, name_suffix),
                        "comp_name": "residual{}".format(ahead),
                        "bar": True,
                    }
                )

    npanel = len(components)
    figsize = figsize if figsize else (10, 3 * npanel)
    fig, axes = plt.subplots(npanel, 1, facecolor="w", figsize=figsize)
    if npanel == 1:
        axes = [axes]
    multiplicative_axes = []
    for ax, comp in zip(axes, components):
        name = comp["plot_name"].lower()
        if (
            "trend" in name
            or ("residuals" in name and "ahead" in name)
            or ("ar" in name and "ahead" in name)
            or ("lagged regressor" in name and "ahead" in name)
        ):
            plot_forecast_component(fcst=fcst, ax=ax, name_suffix=name_suffix, **comp)
        elif "event" in name or "future regressor" in name:
            if "multiplicative" in comp.keys() and comp["multiplicative"]:
                multiplicative_axes.append(ax)
            plot_forecast_component(fcst=fcst, ax=ax, name_suffix=name_suffix, **comp)
        elif "season" in name:
            if m.season_config.mode == "multiplicative":
                multiplicative_axes.append(ax)
            if one_period_per_season:
                comp_name = comp["comp_name"]
                if "weekly" in comp_name.lower() or m.season_config.periods[comp_name].period == 7:
                    plot_weekly(
                        m=m,
                        ax=ax,
                        quantile=quantile,
                        name_suffix=name_suffix,
                        comp_name=comp_name,
                    )
                elif "yearly" in comp_name.lower() or m.season_config.periods[comp_name].period == 365.25:
                    plot_yearly(m=m, ax=ax, quantile=quantile, name_suffix=name_suffix, comp_name=comp_name)
                elif "daily" in comp_name.lower() or m.season_config.periods[comp_name].period == 1:
                    plot_daily(m=m, ax=ax, quantile=quantile, name_suffix=name_suffix, comp_name=comp_name)
                else:
                    plot_custom_season(m=m, ax=ax, name_suffix=name_suffix, quantile=quantile, comp_name=comp_name)
            else:
                comp_name = "season_{}".format(comp["comp_name"])
                plot_forecast_component(
                    fcst=fcst, ax=ax, comp_name=comp_name, name_suffix=name_suffix, plot_name=comp["plot_name"]
                )
        elif "auto-regression" in name or "lagged regressor" in name or "residuals" in name:
            plot_multiforecast_component(fcst=fcst, ax=ax, name_suffix=name_suffix, **comp)

    fig.tight_layout()
    # Reset multiplicative axes labels after tight_layout adjustment
    for ax in multiplicative_axes:
        ax = set_y_as_percent(ax)
    return fig


def plot_forecast_component(
    fcst,
    comp_name,
    name_suffix="",
    plot_name=None,
    ax=None,
    figsize=(10, 6),
    multiplicative=False,
    bar=False,
    rolling=None,
    add_x=False,
):
    """Plot a particular component of the forecast.

    Args:
        fcst (pd.DataFrame):  output of m.predict.
        comp_name (str): Name of the component to plot.
        name_suffix (str): The suffix to be added to the comp_name
        plot_name (str): Name of the plot Title.
        ax (matplotlib axis): matplotlib Axes to plot on.
        figsize (tuple): width, height in inches. Ignored if ax is not None.
            default: (10, 6)
        multiplicative (bool): set y axis as percentage
        bar (bool): make barplot
        rolling (int): rolling average underplot
        add_x (bool): add x symbols to plotted points

    Returns:
        a list of matplotlib artists
    """
    fcst = fcst.fillna(value=np.nan)
    artists = []
    if not ax:
        fig = plt.figure(facecolor="w", figsize=figsize)
        ax = fig.add_subplot(111)
    fcst_t = fcst["ds"].dt.to_pydatetime()
    if rolling is not None:
        rolling_avg = fcst[comp_name + name_suffix].rolling(rolling, min_periods=1, center=True).mean()
        if bar:
            artists += ax.bar(fcst_t, rolling_avg, width=1.00, color="#0072B2", alpha=0.5)
        else:
            artists += ax.plot(fcst_t, rolling_avg, ls="-", color="#0072B2", alpha=0.5)
            if add_x:
                artists += ax.plot(fcst_t, fcst[comp_name + name_suffix], "bx")
    y = fcst[comp_name + name_suffix].values
    if "residual" in comp_name:
        y[-1] = 0
    if bar:
        artists += ax.bar(fcst_t, y, width=1.00, color="#0072B2")
    else:
        artists += ax.plot(fcst_t, y, ls="-", c="#0072B2")
        if add_x or sum(fcst[comp_name + name_suffix].notna()) == 1:
            artists += ax.plot(fcst_t, y, "bx")
    # Specify formatting to workaround matplotlib issue #12925
    locator = AutoDateLocator(interval_multiples=False)
    formatter = AutoDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    ax.grid(True, which="major", c="gray", ls="-", lw=1, alpha=0.2)
    ax.set_xlabel("ds")
    if plot_name is None:
        plot_name = comp_name + name_suffix
    ax.set_ylabel(plot_name)
    if multiplicative:
        ax = set_y_as_percent(ax)
    return artists


def plot_multiforecast_component(
    fcst,
    comp_name,
    name_suffix="",
    plot_name=None,
    ax=None,
    figsize=(10, 6),
    multiplicative=False,
    bar=False,
    focus=1,
    num_overplot=None,
):
    """Plot a particular component of the forecast.

    Args:
        fcst (pd.DataFrame):  output of m.predict.
        comp_name (str): Name of the component to plot.
        name_suffix (str): The suffix to be added to the comp_name
        plot_name (str): Name of the plot Title.
        ax (matplotlib axis): matplotlib Axes to plot on.
        figsize (tuple): width, height in inches. Ignored if ax is not None.
             default: (10, 6)
        multiplicative (bool): set y axis as percentage
        bar (bool): make barplot
        focus (int): forecast number to portray in detail.
        num_overplot (int): overplot all forecasts up to num
            None (default): only plot focus

    Returns:
        a list of matplotlib artists
    """
    artists = []
    if not ax:
        fig = plt.figure(facecolor="w", figsize=figsize)
        ax = fig.add_subplot(111)
    fcst_t = fcst["ds"].dt.to_pydatetime()
    col_names = [col_name for col_name in fcst.columns if col_name.startswith(comp_name)]
    if num_overplot is not None:
        assert num_overplot <= len(col_names)
        for i in list(range(num_overplot))[::-1]:
            y = fcst["{}{}{}".format(comp_name, i + 1, name_suffix)]
            notnull = y.notnull()
            y = y.values
            alpha_min = 0.2
            alpha_softness = 1.2
            alpha = alpha_min + alpha_softness * (1.0 - alpha_min) / (i + 1.0 * alpha_softness)
            if "residual" not in comp_name:
                pass
                # fcst_t=fcst_t[notnull]
                # y = y[notnull]
            else:
                y[-1] = 0
            if bar:
                artists += ax.bar(fcst_t, y, width=1.00, color="#0072B2", alpha=alpha)
            else:
                artists += ax.plot(fcst_t, y, ls="-", color="#0072B2", alpha=alpha)
    if num_overplot is None or focus > 1:
        y = fcst["{}{}{}".format(comp_name, focus, name_suffix)]
        notnull = y.notnull()
        y = y.values
        if "residual" not in comp_name:
            fcst_t = fcst_t[notnull]
            y = y[notnull]
        else:
            y[-1] = 0
        if bar:
            artists += ax.bar(fcst_t, y, width=1.00, color="b")
        else:
            artists += ax.plot(fcst_t, y, ls="-", color="b")
    # Specify formatting to workaround matplotlib issue #12925
    locator = AutoDateLocator(interval_multiples=False)
    formatter = AutoDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    ax.grid(True, which="major", color="gray", ls="-", lw=1, alpha=0.2)
    ax.set_xlabel("ds")
    if plot_name is None:
        plot_name = comp_name + name_suffix
    ax.set_ylabel(plot_name)
    if multiplicative:
        ax = set_y_as_percent(ax)
    return artists
