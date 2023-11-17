import dlib
import cv2

detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor(args["shape_predictor"])



img = dlib.load_rgb_image('g:/1/2.png')
gray = dlib.rgb_to_gray(img)

dets = detector(gray,1)