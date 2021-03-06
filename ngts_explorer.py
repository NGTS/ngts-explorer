#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pymysql
import fitsio
from collections import defaultdict, namedtuple
from pylab import *
import os
from contextlib import contextmanager
import logging
from socket import gethostname
from scipy import signal, stats
import seaborn as sns

sns.set(rc={'lines.markeredgewidth': 0.01})

__all__ = ['NGTSExplorer']

FileData = namedtuple('FileData', ['mjd', 'flux', 'fluxerr',
                                   'airmass'])

class PowerSeries(namedtuple('PowerSeriesBase', ['period', 'power'])):
    @property
    def peak_period(self):
        return self.period[self.power == self.power.max()][0]

@contextmanager
def connect_to_database():
    if gethostname() in ['mbp.local', 'mbp.lan', 'mbp15.local', 'mbp15.lan']:
        host = 'localhost'
    else:
        host = 'ngtsdb'

    with pymysql.connect(user='sw', host=host, db='swdb') as cursor:
        yield cursor

def sin_fn(x, amp, period, epoch, const):
    return amp * np.sin(2. * np.pi * x / period - epoch) + const

def correct_for_airmass(flux, fluxerr, airmass):
    imag_err = 1.08 * fluxerr / flux
    imag = -2.5 * np.log10(flux)

    fit = np.poly1d(np.polyfit(airmass, imag, 1,
                               w=1. / imag_err ** 2))

    model = fit(airmass)
    return imag - model

def build_object_type_mapping(fname):
    with fitsio.FITS(fname) as infile:
        catalogue = infile[1].read()

    mapping = defaultdict(list)
    for row in catalogue:
        try:
            obj_id = row['MAIN_ID'].strip()
        except IndexError:
            obj_id = row['main_id'].strip()

        try:
            otype = row['OTYPE'].strip()
        except IndexError:
            otype = row['otype'].strip()

        vmag = row['V']
        vmag = vmag if vmag == vmag else None

        seq_no = row['Sequence_number']
        mapping[otype].append((
            obj_id,
            long(row['Sequence_number']),
            vmag,
        ))

    return mapping

def fetch_airmass(image_ids):
    image_ids = map(long, image_ids)
    with connect_to_database() as cursor:
        cursor.execute('''select image_id, airmass from headers
                       where image_id in %s''', (image_ids,))
        airmass_mapping = { image_id: airmass
                           for (image_id, airmass) in cursor }

    return np.array([airmass_mapping[i] for i in image_ids])

def extract_data(fname, index):
    file_index = index - 1
    with fitsio.FITS(fname) as infile:
        imagelist = infile['imagelist']
        image_id = imagelist['image_id'].read()
        mjd = imagelist['tmid'].read()

        flux = infile['flux'][file_index:file_index+1, :].flatten()
        fluxerr = infile['fluxerr'][file_index:file_index+1, :].flatten()

    ind = np.argsort(mjd)
    mjd, image_id, flux, fluxerr = [data[ind] for data in [
        mjd, image_id, flux, fluxerr]
    ]

    airmass = fetch_airmass(image_id)

    return FileData(mjd, flux, fluxerr, airmass)


def detrend(extracted_data):
    magerr = 1.08 * extracted_data.fluxerr / extracted_data.flux
    mag = correct_for_airmass(extracted_data.flux, extracted_data.fluxerr,
                              extracted_data.airmass)

    return FileData(extracted_data.mjd, mag, magerr, extracted_data.airmass)

def plot_index(o, detrend_data=False):
    if detrend_data:
        d = detrend(o)
    else:
        d = o

    mjd0 = int(d.mjd.min())
    plt.errorbar(d.mjd - mjd0, d.flux, d.fluxerr, ls='None', marker='.',
                 capsize=0.)

    if detrend_data:
        plt.gca().invert_yaxis()

    if detrend_data:
        plt.ylabel(r'Magnitudes')
    else:
        plt.ylabel(r'Instrmuental flux / $e^- s^{-1}$')

    plt.tight_layout()

def yes_or_no(query):
    result = raw_input(query)
    return result.lower().strip() in ['y', 'ye', 'yes']

def savefig(ob_name, ob_class, outdir='objects'):
    full_out_path = os.path.join(
        outdir, ob_class
    )
    if not os.path.isdir(full_out_path):
        os.makedirs(full_out_path)

    out_filename = os.path.join(full_out_path, '{name}.png'.format(name=ob_name))
    if os.path.isfile(out_filename):
        if yes_or_no(
            'File \'{fname}\' exists, overwrite? [y/N] '.format(
                fname=out_filename)):
            plt.savefig(out_filename, bbox_inches='tight')
    else:
        plt.savefig(out_filename, bbox_inches='tight')

def compute_power_series(data, min_period, max_period, n=250):
    periods = np.linspace(min_period, max_period, n)
    assert (periods > 0).all(), "Periods must be greater than 0"
    freqs = 2. * np.pi / periods

    med_flux = np.median(data.flux)
    power = signal.lombscargle(data.mjd.astype(float),
                               (data.flux - med_flux).astype(float),
                               freqs)

    return PowerSeries(periods, power)

def plot_power_series(power_series):
    plt.plot(power_series.period, power_series.power)
    plt.xlabel(r'Period / d')
    plt.ylabel('Power')
    plt.tight_layout()
    

class NGTSExplorer(object):
    def __init__(self, match_file, data_file):
        self.match_file = match_file
        self.data_file = data_file
        self.name = None
        self.i = None
        self.obclass = None
        self.vmag = None

        self.mapping = build_object_type_mapping(self.match_file)

    def keys(self):
        return self.mapping.keys()

    def set_object(self, obclass, index=0):
        self.name, self.i, self.vmag = self.mapping[obclass][index]
        self.obclass = obclass
        self.data = extract_data(self.data_file, self.i)
        print('{n:d} {obclass} objects'.format(
            n=self.nobjects(self.obclass),
            obclass=self.obclass))
        return self

    def nobjects(self, obclass=None):
        if obclass:
            return len(self.mapping[obclass])
        else:
            return len(self.mapping[self.obclass])

    def mjd_label(self):
        mjd0 = int(self.data.mjd.min())
        return 'MJD - {}'.format(mjd0)

    def plot(self, detrend_data=False):
        self.plot_index(detrend_data)
        plt.xlabel(self.mjd_label())
        plt.tight_layout()
        return self

    def plot_phase(self, period, epoch=0., mjd=True, detrend_data=False,
                   double_plot=True):
        if not mjd:
            epoch -= 2400000.5

        phase = ((self.data.mjd - epoch) / period) % 1
        ind = np.argsort(phase)
        new_data = FileData(phase[ind],
                            self.data.flux[ind],
                            self.data.fluxerr[ind],
                            self.data.airmass[ind]
        )

        if double_plot:
            new_data = FileData(
                np.concatenate([new_data.mjd, new_data.mjd + 1.]),
                np.concatenate([new_data.flux, new_data.flux]),
                np.concatenate([new_data.fluxerr, new_data.fluxerr]),
                np.concatenate([new_data.airmass, new_data.airmass]),
            )

        self.plot_with_title(new_data, detrend_data)
        plt.xlabel(r'Orbital phase')
        plt.tight_layout()
        return self

    def plot_index(self, detrend_data=False):
        self.plot_with_title(self.data, detrend_data)
        return self

    def plot_with_title(self, data, detrend_data=False):
        plot_index(data, detrend_data)
        title = None
        if self.name and self.obclass:
            if self.vmag:
                title = '{name} ({obclass}, V={vmag:.2f})'.format(
                    name=self.name,
                    obclass=self.obclass,
                    vmag=self.vmag
                )
            else:
                title = '{name} ({obclass})'.format(
                    name=self.name,
                    obclass=self.obclass,
                )

        if title:
            plt.title(title)
        return self


    def savefig_index(self, ob_name, ob_class, outdir='objects'):
        savefig(ob_name, ob_class, outdir)
        return self

    def savefig(self, outdir='objects'):
        if not plt.get_fignums():
            raise RuntimeError("Please show the plot window with #plot")

        if self.name is None or self.obclass is None:
            msg = """Please either use #savefig_index or set the object index
            using #set_object before calling this method"""
            raise RuntimeError(msg)

        self.savefig_index(self.name, self.obclass, outdir=outdir)
        return self

    def plot_all(self, obclass, detrend_data=False):
        nobjects = len(self.mapping[obclass])
        print("Plotting a total of {nobjects} objects".format(
            nobjects=nobjects))

        for i in xrange(nobjects):
            print('Plotting object {i}'.format(i=i))
            self.set_object(obclass, index=i).plot(detrend_data=detrend_data)
            raw_input("Press enter to continue")
            plt.close(plt.gcf())

    def find_period(self, min_period=0.1, max_period=1., n=250, plot=True):
        '''
        Computes a lomb scargle periodogram to find the peak period. This
        method returns a PowerSeries object with a `peak_period` property. This
        can then be fed into `plot_phase` for plotting.
        '''
        ps = compute_power_series(self.data, min_period, max_period, n)
        if plot:
            plot_power_series(ps)
        return ps

def launch_interpreter():
    header = '''== NGTS Explorer

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
    '''
    import IPython
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--match', required=False)
    parser.add_argument('--data', required=False)
    args = parser.parse_args()

    if args.match is not None and args.data is not None:
        n = NGTSExplorer(args.match, args.data)
        header += '''
----

Data has been loaded into the n object which is an `NGTSExplorer` instance

Available object classes: {classes}
        '''.format(
            classes=n.keys(),
        )

    plt.ion()
    IPython.embed(banner1='', header=header)

if __name__ == '__main__':
    launch_interpreter()
