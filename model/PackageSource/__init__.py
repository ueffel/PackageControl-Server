import os.path
import glob

modules = glob.glob("{}/*.py".format(os.path.dirname(__file__)))
__all__ = [os.path.basename(f)[:-3] for f in modules
           if os.path.isfile(f) and f != __file__]
