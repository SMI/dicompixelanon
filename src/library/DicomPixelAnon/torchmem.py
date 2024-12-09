""" A utility to import torch for PyTorch,
which limits the amount of memory used, thus allowing
multiple processes to run concurrently.
"""
# Limit the amount of memory used by a PyTorch process.
# This prevents the cache from growing into all available memory,
# thus allowing multiple processes to run in parallel.
# Fraction is currently set to 0.4 which allows two processes.
# This should be imported before any pytorch functions are called.
# If pytorch is not installed, too old, or CPU-only  then nothing happens.

try:
    import torch
    torch.cuda.set_per_process_memory_fraction(0.4, 0)
except ModuleNotFoundError:
    # Ignore if torch not installed
    pass
except AttributeError:
    # Ignore if torch too old so function missing
    pass
except AssertionError as e:
    # Ignore if a CPU version of CUDA
    if str(e) == "Torch not compiled with CUDA enabled":
        pass
    else:
        raise
except RuntimeError as e:
    # Ignore if no NVIDIA driver installed
    if 'no NVIDIA driver' in str(e):
        pass
    else:
        raise
except Exception as e:
    raise
