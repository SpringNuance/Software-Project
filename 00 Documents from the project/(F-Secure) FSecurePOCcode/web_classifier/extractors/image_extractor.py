import numpy as np
import scipy
from PIL import Image
from sklearn.cluster import MiniBatchKMeans


class ImageExtractor:
    @staticmethod
    def get_dominant_colors(image: Image, n: int = 3, palette_size: int = 16):
        # From: https://stackoverflow.com/questions/3241929/python-find-dominant-most-common-color-in-an-image
        # Seems "fast" and sufficient for prototyping.
        # @TODO: Test more advanced and optimized methods.

        image = image.resize((palette_size, palette_size))  # optional, to reduce time
        ar = np.asarray(image)
        shape = ar.shape
        ar = ar.reshape(np.product(shape[:2]), shape[2]).astype(float)

        kmeans = MiniBatchKMeans(n_clusters=10, init="k-means++", n_init="auto", max_iter=20, random_state=1000).fit(ar)
        codes = kmeans.cluster_centers_

        vecs, _dist = scipy.cluster.vq.vq(ar, codes)  # assign codes
        counts, _bins = np.histogram(vecs, len(codes))  # count occurrences

        colors = []
        for index in np.argsort(counts)[::-1]:
            colors.append(tuple([int(code) for code in codes[index]]))
        return colors[:n]
