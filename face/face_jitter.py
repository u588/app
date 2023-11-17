# 人脸微调
import sys
import dlib

def show_jittered_images(window, jittered_images):
    '''
        Shows the specified jittered images one by one
    '''
    for img in jittered_images:
        window.set_image(img)
        dlib.hit_enter_to_continue()

if len(sys.argv) != 2:
    print(
        "Call this program like this:\n"
        "   ./face_jitter.py shape_predictor_5_face_landmarks.dat\n"
        "You can download a trained facial shape predictor from:\n"
        "    http://dlib.net/files/shape_predictor_5_face_landmarks.dat.bz2\n")
    exit()

predictor_path = sys.argv[1]
face_file_path = "g:/1/3.png"

# Load all the models we need: a detector to find the faces, a shape predictor
# to find face landmarks so we can precisely localize the face
detector = dlib.get_frontal_face_detector()
sp = dlib.shape_predictor(predictor_path)

# Load the image using dlib
img = dlib.load_rgb_image(face_file_path)

# Ask the detector to find the bounding boxes of each face.
dets = detector(img)

num_faces = len(dets)

# Find the 5 face landmarks we need to do the alignment.
faces = dlib.full_object_detections()
for detection in dets:
    faces.append(sp(img, detection))

# Get the aligned face image and show it
image = dlib.get_face_chip(img, faces[0], size=320)
window = dlib.image_window()
window.set_image(image)
dlib.hit_enter_to_continue()

# Show 5 jittered images without data augmentation
jittered_images = dlib.jitter_image(image, num_jitters=5)
show_jittered_images(window, jittered_images)

# Show 5 jittered images with data augmentation
jittered_images = dlib.jitter_image(image, num_jitters=5, disturb_colors=True)
show_jittered_images(window, jittered_images)