import dlib

detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("g:/1/shape_predictor_68_face_landmarks.dat")
# Load image
img = dlib.load_rgb_image("g:/1/2.png")
# Detect faces in the image
detections = detector(img, 1)
for k, d in enumerate(detections):
# Get facial landmarks
    shape = predictor(img, d)
# Draw landmarks on the image
for i in range(68):
    pos = shape.part(i)
dlib.draw_circle(img, pos.x, pos.y, 2, dlib.rgb(255,0,255))
# Save the image
dlib.save_image(img, "result.jpg")