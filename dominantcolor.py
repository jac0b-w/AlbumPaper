from PIL import Image
import numpy as np
import scipy
import scipy.misc
import scipy.cluster


def dominant_color(image):
    NUM_CLUSTERS = 5

    image = image.resize((150, 150))      # optional, to reduce time
    ar = np.asarray(image)
    shape = ar.shape
    ar = ar.reshape(scipy.product(shape[:2]), shape[2]).astype(float)

    codes, dist = scipy.cluster.vq.kmeans(ar, NUM_CLUSTERS)

    vecs, dist = scipy.cluster.vq.vq(ar, codes)         # assign codes
    counts, bins = scipy.histogram(vecs, len(codes))    # count occurrences

    index_max = scipy.argmax(counts)                    # find most frequent
    color = tuple([int(code) for code in codes[index_max]])
    return color