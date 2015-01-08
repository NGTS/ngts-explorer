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

Coming soon!

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
