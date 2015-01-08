# NGTS Explorer

For exploring NGTS data by picking out known interesting objects from SIMBAD and plotting. This code allows for nice lightcurves to be generated and interesting features to be found.

## Requirements

The program requires the following python packages:

* `ipython`
* `scipy`
* `matplotlib`
* `numpy`
* `fitsio`
* `pymysql`
* `seaborn`

I recommend the [anaconda python distribution](http://continuum.io/downloads). `fitsio` and `pymysql` are installed using `pip`:

``` sh
pip install fitsio pymysql
```

The others can be installed with `conda`:

``` sh
conda install --yes ipython scipy matplotlib numpy seaborn
```

Currently it uses a connection to a mysql database which may not be available. The code will therefore not run but can be read.

## Usage

The main script `ngts_explorer.py` is run as a standalone script: `python ngts_explorer.py` which sets up the IPython environment.

Optionally the arguments `--match` and `--data` refering to the [simbad](http://simbad.u-strasbg.fr/simbad/) crossmatched file, and NGTS photometry respectively will set up the `NGTSExplorer` object and load it as `n` into the namespace.

Either method prints some help text to the console to get you started:

```
== NGTS Explorer

Explore NGTS data.

The `NGTSExplorer` class is created with a crossmatch file and data file with lightcurves:

>>> n = NGTSExplorer('match.fits', 'data.fits')

=== Plotting

Lightcurves can be plotted against mjd with `#plot`, or in phase with `#plot_phase(period)`. Both
methods take a `detrend_data` boolean argument and remove airmass trends.

=== Period finding

Periods can be found with `NGTSExplorer#find_period`. This plots and computes a Lomb-Scargle
periodogram and returns a `PowerSeries` object, with a `peak_period` property. This can then easily
be used with `#plot_phase`:

>>> p = n.find_period()
>>> n.plot_phase(p.peak_period)

=== Choosing an object

`NGTSExplorer#keys` contains the unique SIMBAD object classes, and an object is chosen with
`#set_object(key, index=0)`.
```

## Todo

* Add ability to search by object identifier
  * `NGTSExplorer` can have `#show_object` method which shows a particular object by (fuzzy?) name
  * when building the mapping object, store the mapping from object name to identifier
    * then just call the standard api
    * when given the name, look up the object id and plot to screen
  * perhaps add fuzzy searching
* flesh out the way to plot all objects in a class and save chosen ones
  * perhaps some form of ui in which the user can save the image
* Improve the period finding
* Add ability to add binned data
* Allow for choosing of subset of data
