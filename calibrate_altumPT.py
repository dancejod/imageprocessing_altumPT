import matplotlib.pyplot as plt
import micasense.metadata as metadata
import sys
import glob
import micasense.capture as capture
import numpy as np
import subprocess
import micasense.utils as msutils
import tifffile
import logging
from timeit import default_timer as timer
from datetime import timedelta
from pathlib import Path
from tqdm import tqdm

###PROCESSING BLUE TO NIR BANDS ONLY, i do not particularly care about the rest rn
###Place everything including panel images to one folder, include all images
#TODO: make more robust for additional bands

def run(*args):
    root_path = Path(args[0])

    outpath = root_path.parent / "images"
    outpath.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        handlers=[
            logging.FileHandler(outpath / "log.txt", mode="w"),
            logging.StreamHandler(sys.stdout)
        ],
        force=True
    )
    logger = logging.getLogger()

    def retrieve_panel_irradiances(panel_cap, ref_reflectances):
        try:
            panel_irradiances = panel_cap.panel_irradiance(ref_reflectances)
            return panel_irradiances
        except Exception:
            logger.warning("Calibration panel not detected")
            return None

    #our panel reflectances
    ALTUMPT_REFLECTANCE_BY_BAND = [0.508, 0.509, 0.509, 0.509, 0.506]

    imageNames = list(root_path.glob("IMG_*.tif"))
    #skip panchro and thermal
    imageNames = [x.as_posix() for x in imageNames if not (
        x.stem.endswith("6") or x.stem.endswith("_7")
    )]

    #before flight panel images
    panelNamesBefore = imageNames[:5]
    panelCapBefore = capture.Capture.from_filelist(panelNamesBefore)

    #after flight panel images
    panelNamesAfter = imageNames[-5:]
    panelCapAfter = capture.Capture.from_filelist(panelNamesAfter)

    panelIrradiancesBefore = retrieve_panel_irradiances(panelCapBefore, ALTUMPT_REFLECTANCE_BY_BAND)
    panelIrradiancesAfter = retrieve_panel_irradiances(panelCapAfter, ALTUMPT_REFLECTANCE_BY_BAND)

    if panelIrradiancesBefore is None and panelIrradiancesAfter is None:
        logger.critical("Houston, we have a problem (no panels detected for current flight)")
        exit()
    elif panelIrradiancesBefore is not None and panelIrradiancesAfter is not None:
        both_panels_present = True
        logger.info("Both panels present for this flight")
        flightImageNames = imageNames[5:-5]
    else:
        both_panels_present = False
        logger.warning("One of the before/after flight panels is not present, working with available panel")
        panelIrradiances = panelIrradiancesAfter if panelIrradiancesAfter is not None else panelIrradiancesBefore
        flightImageNames = imageNames
        
    out_paths = []

    time_start = timer()
    logger.info(f"{'[Calibration]':<15} Started calibrating flight images")

    for i in tqdm(range(0, len(flightImageNames), 5), desc="Processing flight images"):
        imgs = flightImageNames[i:i+5]
        imgsCap = capture.Capture.from_filelist(imgs)

        if both_panels_present:
            band_irradiances = [np.interp(imgsCap.utc_time().timestamp(), [panelCapBefore.utc_time().timestamp(), panelCapAfter.utc_time().timestamp()], [
            panelIrradiancesBefore[b], panelIrradiancesAfter[b]
        ]) for b in range(len(imgsCap.images))]
        
        else:
            band_irradiances = panelIrradiances

        flightReflectanceImages = imgsCap.reflectance(band_irradiances)

        for b, image in enumerate(imgs):
            in_path = Path(image)
            out = outpath / in_path.name
            
            tifffile.imwrite(out, flightReflectanceImages[b].astype("float32"))

            out_paths.append(out)

    time_end = timer()
    logger.info(f"{'[Calibration]':<15} Calibrated in: {timedelta(seconds=time_end - time_start)}")

    exiftime_start = timer()
    logger.info(f"{'[EXIF]':<15} Updating metadata of calibrated images...")
    subprocess.run(["exiftool", "-config", "altumconfigexif.cfg", "-tagsfromfile", f"{root_path}/%f.tif", outpath, "-xmp:all","-gps:all", "-overwrite_original"])
    exiftime_end = timer()
    logger.info(f"{'[EXIF]':<15} Image metadata updated in: {timedelta(seconds=exiftime_end - exiftime_start)}")

    logger.info(f"{'[Done]':<15} Successfully calibrated {len(flightImageNames)} flight images")

if __name__ == "__main__":
    run(sys.argv[1])