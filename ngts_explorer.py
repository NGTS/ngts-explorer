import pymysql
import fitsio
from collections import defaultdict, namedtuple
import numpy as np
import matplotlib.pyplot as plt
import os

FileData = namedtuple('FileData', ['mjd', 'flux', 'fluxerr',
                                   'airmass'])

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
    with pymysql.connect(user='sw', db='swdb') as cursor:
        cursor.execute('''select image_id, airmass from headers
                       where image_id in %s''', (image_ids,))
        airmass_mapping = { image_id: airmass
                           for (image_id, airmass) in cursor }

    return np.array([airmass_mapping[i] for i in image_ids])

def extract_data(fname):
    with fitsio.FITS(fname) as infile:
        imagelist = infile['imagelist']
        image_id = imagelist['image_id'].read()
        mjd = imagelist['tmid'].read()

        flux = infile['flux'].read()
        fluxerr = infile['fluxerr'].read()

    ind = np.argsort(mjd)
    mjd, image_id = [data[ind] for data in [mjd, image_id]]
    flux, fluxerr = [data[:, ind] for data in [flux, fluxerr]]

    airmass = fetch_airmass(image_id)

    return FileData(mjd, flux, fluxerr, airmass)

def retrieve_object(file_data, index):
    file_index = index - 1
    lc = file_data.flux[file_index]
    lcerr = file_data.fluxerr[file_index]

    return FileData(file_data.mjd, lc, lcerr, file_data.airmass)


def detrend(extracted_data):
    magerr = 1.08 * extracted_data.fluxerr / extracted_data.flux
    mag = correct_for_airmass(extracted_data.flux, extracted_data.fluxerr,
                              extracted_data.airmass)

    return FileData(extracted_data.mjd, mag, magerr, extracted_data.airmass)

def plot_index(file_data, index, detrend_data=False):
    o = retrieve_object(file_data, index)
    if detrend_data:
        d = detrend(o)
    else:
        d = o

    mjd0 = int(d.mjd.min())
    plt.errorbar(d.mjd - mjd0, d.flux, d.fluxerr, ls='None', marker='.')

    if detrend_data:
        plt.gca().invert_yaxis()

    plt.xlabel(r'MJD - {}'.format(mjd0))
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
