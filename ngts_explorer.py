import pymysql
import fitsio
from collections import defaultdict, namedtuple
import numpy as np
import matplotlib.pyplot as plt
import os
from contextlib import contextmanager
import logging
from socket import gethostname

__all__ = ['NGTSExplorer']

FileData = namedtuple('FileData', ['mjd', 'flux', 'fluxerr',
                                   'airmass'])

@contextmanager
def connect_to_database():
    if gethostname() in ['mbp.local', 'mbp.lan']:
        host = 'localhost'
    else:
        host = 'ngtsdb'

    with pymysql.connect(user='sw', host=host, db='swdb') as cursor:
        yield cursor

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
        obj_id = row['MAIN_ID'].strip()
        otype = row['OTYPE'].strip()
        seq_no = row['Sequence_number']
        mapping[otype].append((
            obj_id,
            long(row['Sequence_number']),
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
    plt.errorbar(d.mjd - mjd0, d.flux, d.fluxerr, ls='None', marker='.')

    if detrend_data:
        plt.gca().invert_yaxis()

    if detrend_data:
        plt.ylabel(r'Magnitudes')
    else:
        plt.ylabel(r'Instrmuental flux / $e^- s^{-1}$')

    plt.tight_layout()

def savefig(ob_name, ob_class, outdir='objects'):
    full_out_path = os.path.join(
        outdir, ob_class
    )
    if not os.path.isdir(full_out_path):
        os.makedirs(full_out_path)

    plt.savefig(os.path.join(full_out_path, '{name}.png'.format(name=ob_name)),
                bbox_inches='tight')

class NGTSExplorer(object):
    def __init__(self, match_file, data_file):
        self.match_file = match_file
        self.data_file = data_file
        self.name = None
        self.i = None
        self.obclass = None

        self.mapping = build_object_type_mapping(self.match_file)

    def keys(self):
        return self.mapping.keys()

    def set_object(self, obclass, index=0):
        self.name, self.i = self.mapping[obclass][index]
        self.obclass = obclass
        self.data = extract_data(self.data_file, self.i)
        return self

    def mjd_label(self):
        mjd0 = int(self.data.mjd.min())
        return 'MJD - {}'.format(mjd0)

    def plot(self, detrend_data=False):
        self.plot_index(detrend_data)
        plt.xlabel(self.mjd_label())
        plt.tight_layout()
        return self

    def plot_phase(self, period, epoch, mjd=True, detrend_data=False,
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
        if self.name and self.obclass:
            title = '{name} ({obclass})'.format(
                name=self.name,
                obclass=self.obclass
            )
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

        for i in xrange(nobjects):
            self.set_object(obclass, index=i).plot(detrend_data=detrend_data)

    def __getattr__(self, obclass):
        self.plot_all(obclass, detrend_data=False)
