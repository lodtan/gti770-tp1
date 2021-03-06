#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Course :
    GTI770 — Systèmes intelligents et apprentissage machine

Project :
    Lab # 1 - Définition et extraction de primitives

Students :
    LEMARCHANT HUGO - AP85480
    TAN ELODIE - TANE25619607

Group :
    GTI770-A18-0C
"""

import csv
import cv2
import math
import numpy as np
import scipy.ndimage as nd
from scipy.stats.mstats import mquantiles, kurtosis, skew
from sklearn.preprocessing import LabelEncoder


class GalaxyProcessor(object):
    """ Process galaxy images and extract the features."""

    def __init__(self, path):
        self._img_path = path
        self._exts = ".jpg"

    def process_galaxy(self, dataset):
        """ Process a galaxy image.

        Get all the features from a galaxy image.

        Args:
            galaxy_id: a string containing the galaxy ID

        Returns:
             An array containing the image's features.
        """
        features = list()

        for sample, label in zip(dataset.train._img_names, dataset.train._labels):

            # Get the file name associated with the galaxy ID.
            file = self.get_image_path() + str(sample[0]) + ".jpg"

            # Compute the features and append to the list.
            feature_vector = self.get_features(file, sample[0], label[0])
            features.append(feature_vector)

        for sample, label in zip(dataset.valid._img_names, dataset.valid._labels):

            # Get the file name associated with the galaxy ID.
            file = self.get_image_path() + str(sample[0]) + ".jpg"

            # Compute the features and append to the list.
            feature_vector = self.get_features(file, sample[0], label[0])
            features.append(feature_vector)

        return features

    def load_image(self, filepath):
        """ Load an image using OpenCV library.

        Load an image using OpenCV library.

        Args:
            filepath: the path of the file to open.

        Returns:
             An image in OpenCV standard format.
        """
        return cv2.imread(filename=filepath)

    def crop_image(self, image, width, height):
        """ Crop an image.

        Utility method to crop an image using Python arrays.

        Args:
            image: a pointer to an OpenCV image matrix.
            width: the resulting width.
            height: the resulting height.

        Returns:
             A 2D array representing the cropped image.
        """
        return image[width:height, width:height]

    def gaussian_filter(self, image, kernel_width, kernel_height):
        """ Apply a gaussian filter.

        Apply a gaussian filter on an image.

        Args:
            image: an OpenCV standard image format.
            kernel_width: the kernel width of the filter.
            kernel_height: the kernel height of the filter.

        Returns:
             The image with applied gaussian filter.
        """
        return cv2.GaussianBlur(image, (kernel_width, kernel_height), 2.0)

    def rescale(self, image, min=0, max=255):
        """ Rescale the colors of an image.

        Utility method to rescale colors from an image.

        Args:
            image: an OpenCV standard image format.
            min: The minimum color value [0, 255] range.
            max: The maximum color value [0, 255] range.

        Returns:
            The image with rescaled colors.
        """
        image = image.astype('float')
        image -= image.min()
        image /= image.max()
        image = image * (max - min) + min

        return image

    def saturate(self, image, q0=0.01, q1=0.99):
        """ Stretch contrasts of an image.

        Utility method to saturate the contrast of an image.

        Args:
            image: an OpenCV standard image format.
            q0: minimum coefficient.
            q1: maximum coefficient.

        Returns:
            The image with saturated contrasts.
        """
        image = image.astype('float')
        if q0 is None:
            q0 = 0
        if q1 is None:
            q1 = 1
        q = mquantiles(image[np.nonzero(image)].flatten(), [q0, q1])
        image[image < q[0]] = q[0]
        image[image > q[1]] = q[1]

        return image

    def largest_connected_component(self, image, labels, nb_labels):
        """ Select the largest connected component.

        Select the largest connected component which is closest to the center using a weighting size/distance**2.

        Args:
            image: an OpenCV standard image format.
            labels: image labels.
            nb_labels: number of image labels.

        Returns:
            A thresholded image of the largest connected component.
        """
        sizes = np.bincount(labels.flatten(),
                            minlength=nb_labels + 1)
        centers = nd.center_of_mass(image, labels, range(1, nb_labels + 1))

        distances = list(map(lambda args:
                             (image.shape[0] / 2 - args[1]) ** 2 + (image.shape[1] / 2 - args[0]) ** 2,
                             centers))

        distances = [1.0] + distances
        distances = np.array(distances)
        sizes[0] = 0
        sizes[sizes < 20] = 0
        sizes = sizes / (distances + 0.000001)
        best_label = np.argmax(sizes)
        thresholded = (labels == best_label) * 255

        return thresholded

    def recenter(self, image, x, y, interpolation=cv2.INTER_LINEAR):
        """ Recenter an image.

        Recenter an image around x and y.

        Args:
            image: an OpenCV standard image format.
            x: integer representing an "X" coordinate.
            y: integer representing an "Y" coordinate.
            interpoolation: interpolation method.

        Returns:
            The recentered image.
        """
        cx = float(image.shape[1]) / 2
        cy = float(image.shape[0]) / 2

        # Compute the translation matrix.
        translation_matrix = np.array([[1, 0, cx - x], [0, 1, cy - y]], dtype='float32')

        # Compute the afine transform.
        recentered_image = cv2.warpAffine(image, translation_matrix, image.shape[:2], flags=interpolation)

        return recentered_image

    def compose(self, matrix1, matrix2):
        """ Composes affine transformations.

        Compute the resulting transformation matrix based on two supplied transformation matrix.

        Args:
            matrix1: The first matrix transform.
            matrix2: The second matrix transform.

        Returns:
            The composition matrix of the affine transforms.
        """
        n1 = np.eye(3, dtype='float32')
        n2 = np.eye(3, dtype='float32')
        n1[:2] = matrix1
        n2[:2] = matrix2
        n3 = np.dot(n1, n2)

        return n3[:2]

    def rotate(self, image, x, y, angle, interpolation=cv2.INTER_LINEAR):
        """ Rotate an image.

        Rotate an image by an angle in degrees around specific point.

        Source : http://stackoverflow.com/questions/9041681/opencv-python-rotate-image-by-x-degrees-around-specific-point

        Args:
            image: an OpenCV standard image format.
            x: integer representing an "X" coordinate
            y: integer representing an "Y" coordinate.
            angle: the angle of rotation.
            interpolation: interpolation method.

        Returns:
            The rotated image.
        """
        # Get the image center.
        cx = float(image.shape[1]) / 2
        cy = float(image.shape[0]) / 2

        # Compute a translation matrix to recenter the image.
        translation_matrix = np.array([[1, 0, cx - x], [0, 1, cy - y]], dtype='float32')

        # Compute a rotation matrix to rotate the image.
        rotation_matrix = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)

        # Compose the affine transformation.
        m = self.compose(rotation_matrix, translation_matrix)

        # Compute the rotation.
        rotated_image = cv2.warpAffine(image, m, image.shape[:2], flags=interpolation)

        return rotated_image

    def random_colors(self, labels):
        """ Color with random colors components in an image.

        For debug purpose.

        Args:
            labels: some image labels.

        Returns:
            Colored image segment.
        """
        idx = np.nonzero(labels)
        nb_labels = labels.max()
        colors = np.random.random_integers(0, 255, size=(nb_labels + 1, 3))
        seg = np.zeros((labels.shape[0], labels.shape[1], 3), dtype='uint8')
        seg[idx] = colors[labels[idx].astype('int')]

        return seg

    def fit_ellipse(self, points, factor=1.96):
        """  Fit points to ellipse.

        Fit an ellips to points passed in parameters.

        Theorical source : http://en.wikipedia.org/wiki/1.96

        Args:
            points: image points.
            factor: the 1.96 factor in order to contain 95% of the galaxy.

        Returns:
            The center of the ellipse, the singular values, and the angle.

        """
        points = points.astype('float')
        center = points.mean(axis=0)
        points -= center

        U, S, V = np.linalg.svd(points, full_matrices=False)

        S /= np.sqrt(len(points) - 1)
        S *= factor
        angle = math.atan2(V[0, 1], V[0, 0]) / math.pi * 180

        return center, 2 * S, angle

    def gini(self, x):
        """ Get the Gini coefficient.

        The Gini coefficient (sometimes expressed as a Gini ratio or a normalized Gini index)
        is a measure of statistical dispersion and is the most commonly used measure of inequality.

        Source : http://www.ellipsix.net/blog/2012/11/the-gini-coefficient-for-distribution-inequality.html

        Args:
            x: the pixels representing an image.
            filename: filename of the image.
        """

        # requires all values in x to be zero or positive numbers, otherwise results are undefined
        x = x.flatten()
        n = len(x)
        s = x.sum()
        r = np.argsort(np.argsort(-x))  # calculates zero-based ranks
        if s == 0 or n == 0:
            return 1.0
        else:
            return 1.0 - (2.0 * (r * x).sum() + s) / (n * s)

    def get_entropy(self, image):
        """ Get the image's entropy.

        Entropy is a scalar value representing the entropy of grayscale image.
        Entropy is a statistical measure of randomness that can be used to characterize
        the texture of the input image.

        Source : http://stackoverflow.com/questions/16647116/faster-way-to-analyze-each-sub-window-in-an-image

        Args:
            image: an OpenCV standard image format.

        Returns:
            Image's entropy as a floating point value.
        """
        hist = cv2.calcHist([image], [0], None, [256], [0, 256])
        hist = hist.ravel() / hist.sum()
        logs = np.log2(hist + 0.00001)

        return -1 * (hist * logs).sum()

    def get_gray_float_image(self, image):
        """ get image as grey scale image in float format.

        Transform the image into grey scale and transform values into floating point integer.

        Args:
            image: an OpenCV standard color image format.

        Returns:
             Image in gray scale in floating point values.
        """
        return cv2.cvtColor(image.astype("uint8"), cv2.COLOR_BGR2GRAY).astype("float")

    def get_gray_image(self, image):
        """ Get an image in gray scales.

        Transform an image in grey scale. Returns values as integer.

        Args:
            image : an OpenCV standard image format.

        Returns:
             Image in gray scale.
        """
        return cv2.cvtColor(image.astype("uint8"), cv2.COLOR_BGR2GRAY)

    def remove_starlight(self, image_color, image_gray):
        """ Removes the star light in images.

        Calclates the median in color and gray scale image to clean the image's background.

        Args:
             image_color: an OpenCV standard color image format.
             image_gray: an OpenCV standard gray scale image format.

        Returns:
            An image cleaned from star light.
        """
        t = np.max(np.median(image_color[np.nonzero(image_gray)], axis=0))
        image_color[image_color < t] = t

        return self.rescale(image_color).astype("uint8")

    def get_center_of_mass(self, image, labels, nb_labels):
        """ Get the center of mass of the galaxy.


        Args:
            image: an OpenCV standard gray scale image format
            labels: the image's labels
            nb_labels: the image's number of labels

        Returns:
            The thresholded galaxy image with it's center coordinates.
        """
        thresholded = self.largest_connected_component(image=image, labels=labels, nb_labels=nb_labels)
        center = nd.center_of_mass(image, thresholded)

        return thresholded, center

    def get_light_radius(self, image, r=[0.1, 0.8]):
        """ Get the radius of the light in the image.

        Args:
            image: an OpenCV standard gray scale image format
            r: probability list

        Returns:
            The light radius as a floating point value.
        """
        image = image.astype('float')
        idx = np.nonzero(image)
        s = image[idx].sum()
        mask = np.ones(image.shape)
        mask[int(image.shape[0] / 2), int(image.shape[1] / 2)] = 0
        edt = nd.distance_transform_edt(mask)
        edt[edt >= image.shape[1] / 2] = 0
        edt[image == 0] = 0
        q = mquantiles(edt[np.nonzero(edt)].flatten(), r)
        res = []
        for q0 in q:
            res.append(image[edt < q0].sum() / s)

        return res

    def get_color_histogram(self, img_color):
        """ Get the color histograms from a color image.

        Args:
            img_color: an OpenCV standard color image format.

        Returns:
            The BGR color histograms.
        """
        blue_histogram = cv2.calcHist(img_color, [0], None, [256], [0, 256])
        green_histogram = cv2.calcHist(img_color, [1], None, [256], [0, 256])
        red_histogram = cv2.calcHist(img_color, [2], None, [256], [0, 256])

        return np.array([blue_histogram, green_histogram, red_histogram])

    def get_features(self, img_id):
        """ Get the image's features.

        A wrapping method to get the image's features.

        Place your code here.

        Args:
            image_file: the image's file being processed.

        Returns:
            features: a feature vector of N dimensions for N features.
        """

        coherence_threshold = 160**2*0.01
        nb_colors = 64
        img_color = cv2.imread(self._img_path + str(img_id) + self._exts)
        ratio, values  = self.get_ratio_aspect(img_color)
        circularity = self.calculate_circularity(img_color)
        ccv = self.get_ccv(img_color,coherence_threshold,nb_colors)
        features = np.append([ratio, circularity],ccv)
        return features

    def get_ccv(self, image, threshold, nb_colors):

        """
        This feature mark each pixel as belonging to a coherent or incoherent regions.
        A region R of connected pixels satisfy this rule : For each p1, p2 ∈ R,
        there exist a path of adjacent pixels from p1, p2
        (connectedComponentsWithStats is used to retrieve these areas)

        Each pixel is checked for its members to a coherent area/region.
        Coherent pixels are the pixels belonging an areas of size >= threshold
        InCoherent pixels are the pixels an areas of size < threshold

        Args:
            image     : an OpenCV standard color image format.
            threshold : minimum area size for coherent regions
            nb_colors : size of the Color space to discretize the image

        Returns:

            The CCV vector of length 2 * nb_colors.

              C1          |        C2    |...|         CN    |       I1          |      I2    |... | IN
        nb coherent pix   |              |   |               |nb incoherent pix  |            |    |
        for color1        | for color2   |   | for colorN    |for color1         |for color2  |    |for colorN

        """

        def quantize_color(img, nb_colors=64):
            div = 256//nb_colors
            rgb = cv2.split(img)
            quantized_list = []
            # quantize nb_colors colors for each channel
            for ch in rgb:
                vf = np.vectorize(lambda x, div: int(x//div)*div)
                quantized = vf(ch, div)
                quantized_list.append(quantized.astype(np.uint8))
            # Merge the channels after quantization
            d_img = cv2.merge(quantized_list)
            return d_img

        img = image.copy()
        im_color = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img=self.crop_image(im_color, 212-80, 212+80)

        # blur to eliminate slight variations between the adjacent pixels
        img = cv2.GaussianBlur(img, (3, 3), 0)
        # quantize image into nb_colors
        img = quantize_color(img, nb_colors)
        bgr = cv2.split(img)
        coherent_pixels = np.zeros(nb_colors)
        incoherent_pixels = np.zeros(nb_colors)
        # labeling
        for (i, ch) in enumerate(bgr):
            (ret, th) = cv2.threshold(ch, 127, 255, 0)
            (ret, labeled, stat, centroids) = cv2.connectedComponentsWithStats(th, None,cv2.CC_STAT_AREA, None, connectivity=8)
            # generate areas
            areas = [[v[4], label_idx] for (label_idx, v) in enumerate(stat)]
            coords = [[v[0], v[1]] for (label_idx, v) in enumerate(stat)]
            # Counting coherent and incoherent pixels over each area
            for (area, coord) in zip(areas, coords):
                area_size = area[0]
                (x, y) = (coord[0], coord[1])
                if x < ch.shape[1] and y < ch.shape[0]:
                    bin_idx = int(ch[y, x] // (256 // nb_colors))
                    if area_size >= threshold:
                        # COHERENT PIXELS (belong to area >= Threshold pixels )
                        coherent_pixels[bin_idx]+= area_size
                    else:
                        # INCOHERENT PIXELS (belong to area < Threshold pixels )
                        incoherent_pixels[bin_idx]+= area_size
        return [coherent_pixels, incoherent_pixels]

    def get_ratio_aspect(self, image):
        """
        Calculate the ratio of the bounding revtangle containing the largest contoured element. Most of the time the galaxy.
        Args : image read by the cv2.imread function.
        Returns the ratio and the values of width and lenght
        """
        crop = 150
        epsilon = 0.0000000001
        img = image.copy()
        if not isinstance(img, np.ndarray):
            return -1, (None, None)
        img = img[212-crop:212+crop, 212-crop:212+crop]
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ret,thresh = cv2.threshold(img,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
        im2,contours,hierarchy = cv2.findContours(thresh, 2, 2)
        cnt = max(contours, key = lambda cnt : len(cnt))
        rect = cv2.minAreaRect(cnt)
        ratio = rect[1][0]/(rect[1][1]+epsilon)
        #print("ratio = {}".format(ratio))
        return ratio, (rect[1][0], rect[1][1])

    def calculate_circularity(self, image):
        """calculateCircularity
        Fonction calculant la circularité d'une image de galaxie grâce à la fonction C = 4pi * A/P2.
        Args:
            img: L'image pour laquelle nous voulons calculer la circularité.
        Returns:
            circularity: La valeur de retour. Elle est définie entre 0 et 1.
                        Plus la valeur est proche de 1, plus la galaxie est circulaire.

        """
        img = image.copy()
        img = self.crop_image(img, 212-85, 212+85)
        log = nd.gaussian_laplace(img, sigma=20)
        img = img - log
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY);
        ret, thresh = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
        kernel = np.ones((3,3),np.uint8)
        dilation = cv2.dilate(thresh,kernel,iterations = 1)
        # Get moment to calculate area
        img2, contours, hierarchy = cv2.findContours(dilation, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contour = max(contours, key = lambda cnt : len(cnt))
        area = cv2.moments(contour)['m00']
        #Get perimeter :
        perimeter = cv2.arcLength(contour,True)
        # Circularity
        circularity = 4 * math.pi * area / (perimeter**2)
        return circularity
