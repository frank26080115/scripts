'''
This script will take a directory of images and turn it into a webp animation
The user is required to install libwebp binaries first, also ffmpeg binaries are also required
The paths to the binaries need to be specified within the script

Only tested on Windows so far
'''

import argparse
import sys, os, glob, subprocess, re

# specify paths to required binaries
PATH_IMG2WEBP = r"C:\ProgramFiles\libwebp-1.2.3-windows-x64\bin\img2webp.exe"
PATH_FFMPEG   = r"C:\ProgramFiles\ffmpeg-4.4-full_build\bin\ffmpeg.exe"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dir"                       , type=str                          , help="directory containing image files to animate")
    parser.add_argument("outfile"                   , type=str                          , help="output file name/path (use #dir/ to prepend the input dir path)")
    parser.add_argument("--video"                   , type=str                          , help="video file path (ffmpeg will split video to frames first)")
    parser.add_argument("-d"        , "--frmdly"    , type=int           , default=-1   , help="frame delay in milliseconds (default 100)")
    parser.add_argument("-lossy"                    , action="store_true"               , help="use lossy compression")
    parser.add_argument("-lossless"                 , action="store_true"               , help="use lossless compression")
    parser.add_argument("-q"        , "--quality"   , type=float         , default=75.0 , help="quality 0 to 100 (default 75)")
    parser.add_argument("-m"        , "--method"    , type=int           , default=4    , help="method 0 to 6 (default 4)")
    parser.add_argument("-loop"     , "--loop"      , type=int           , default=0    , help="times to loop, 0 = inf (default 0)")
    parser.add_argument("-sortrev"                  , action="store_true"               , help="reverse the file sort")
    parser.add_argument("-skip"                     , type=int           , default=0    , help="skip frames")
    parser.add_argument("-resize"                   , type=str                          , help="resize images WxH")
    parser.add_argument("-crop"                     , type=str                          , help="crop images X,Y,W,H")
    parser.add_argument("-v"        , "--verbose"   , action="store_true"               , help="verbose messages")
    args = parser.parse_args()

    vid_fps = None

    dir = os.path.abspath(args.dir)
    if args.video is not None: # user specified a video file

        # make directory for the split frames
        if not os.path.isdir(dir):
            os.makedirs(dir, exist_ok=True)

        # use FFMPEG to split the video into individual frames

        call_args = [PATH_FFMPEG]
        call_args.append("-i")
        call_args.append(args.video)
        call_args.append(dir + os.path.sep + "%08d.png")
        if args.verbose:
            s = "Calling: ffmpeg"
            for ar in call_args[1:]:
                s += " " + ar
            print(s)
        p = subprocess.run(call_args, capture_output=True)

        # obtain the text that FFMPEG outputs, we need the frame rate FPS number to correctly convert into an animation

        s = p.stdout.decode()
        s += p.stderr.decode()
        if args.verbose:
            print(s)

        # use regular expressions to find the frame rate FPS number
        r = r"(.*)(Stream)(.*)([^0-9])([0-9]+)(\s*)(fps,)(.*)"
        m = re.search(r, s)
        if m:
            vid_fps = int(m.group(5))
            if args.verbose:
                print("Video FPS: %u" % vid_fps)

        if not args.verbose:
            print("Video processed \"%s\" -> \"%s\"" % (args.video, dir))
    else:
        if not os.path.isdir(dir):
            raise Exception("ERROR: directory specified \"%s\" is not a valid directory" % dir)
            return 1

    # get all of the relavent image files in the directory
    fexts = ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.tif", "*.tiff", "*.webp"]
    files = []
    for ext in fexts:
        g = glob.glob(os.path.join(dir, ext))
        for gi in g:
            if gi not in files:
                files.append(gi)
        g = glob.glob(os.path.join(dir, ext.lower()))
        for gi in g:
            if gi not in files:
                files.append(gi)
        g = glob.glob(os.path.join(dir, ext.upper()))
        for gi in g:
            if gi not in files:
                files.append(gi)

    # assume webpinfo is in the same directory as img2webp
    if os.name == 'nt':
        path_webpinfo = PATH_IMG2WEBP.replace("img2webp.exe", "webpinfo.exe")
    else:
        path_webpinfo = PATH_IMG2WEBP.replace("img2webp", "webpinfo")

    # since we can't add webp animations into a new animation, we need to filter them out
    for f in files:
        if f.lower().endswith(".webp"):
            call_args = [path_webpinfo]
            call_args.append(f)
            r = subprocess.run(call_args, capture_output=True, text=True)
            s = r.stdout
            s += " " + r.stderr
            # check if it is an animation
            if " ANMF " in s:
                files.remove(f)
                if args.verbose:
                    print("removed animated WebP file \"%s\" from file list" % os.path.basename(f))

    if (hasattr(args, "resize") and args.resize is not None) or (hasattr(args, "crop") and args.crop is not None):
        resize_width = -1
        resize_height = -1
        if (hasattr(args, "resize") and args.resize is not None):
            # parse user specified resizing parameter
            resize_str    = args.resize
            resize_parts  = resize_str.split('x')
            resize_width  = int(resize_parts[0])
            resize_height = int(resize_parts[1])
        crop_x = -1
        crop_y = -1
        crop_w = -1
        crop_h = -1
        if (hasattr(args, "crop") and args.crop is not None):
            # parse user specified cropping parameter
            crop_str    = args.crop
            crop_parts  = crop_str.split(',')
            crop_x      = int(crop_parts[0])
            crop_y      = int(crop_parts[1])
            crop_w      = int(crop_parts[2])
            crop_h      = int(crop_parts[3])
        tmpdir = os.path.join(dir, "tmp_resize_" + args.resize)
        os.makedirs(tmpdir, exist_ok=True)
        if args.verbose:
            print("resizing to %u x %u , stored at \"%s\"" % (resize_width, resize_height, tmpdir))

        # assume cwebp is in the same directory as img2webp
        if os.name == 'nt':
            path_cwebp = PATH_IMG2WEBP.replace("img2webp.exe", "cwebp.exe")
        else:
            path_cwebp = PATH_IMG2WEBP.replace("img2webp", "cwebp")

        # for each file, apply resizing and cropping, and output to a webp file
        # this is done through the cwebp application
        files2 = []
        for f in files:
            nfpath = os.path.join(tmpdir, os.path.splitext(os.path.basename(f))[0]) + ".webp"
            call_args = [path_cwebp]
            call_args.append("-lossless")
            if resize_width >= 0: # parameter exsits
                call_args.append("-resize")
                call_args.append(str(resize_width))
                call_args.append(str(resize_height))
            if crop_x >= 0: # parameter exsits
                call_args.append("-crop")
                call_args.append(str(crop_x))
                call_args.append(str(crop_y))
                call_args.append(str(crop_w))
                call_args.append(str(crop_h))
            call_args.append(f)
            call_args.append("-o")
            call_args.append(nfpath)
            subprocess.run(call_args)
            files2.append(nfpath)
        files = files2

    # sort the files in alphabetical order, which means it'll be nice if they were numbered in sequence
    files.sort(reverse=args.sortrev)
    print("Directory \"%s\" found %u files" % (dir, len(files)))
    if args.verbose:
        for f in files:
            print(" -> %s" % f)

    # finally, use img2webp to make the animation
    call_args = [PATH_IMG2WEBP]

    # always loop
    call_args.append("-loop")
    call_args.append("%u" % args.loop)

    if vid_fps is not None and args.frmdly <= 0:
        # use video frame rate
        frmdly = round(1000 / vid_fps)
    else:
        # use user specified frame delay parameter
        frmdly = 100 if args.frmdly < 0 else args.frmdly

    cnt = 0
    for f in files:

        if args.skip > 1 and (cnt % args.skip) != 0:
            # should skip this frame
            cnt += 1
            continue

        # apply required parameters to this frame
        call_args.append("-d")
        call_args.append("%u" % frmdly)
        if args.lossy:
            call_args.append("-lossy")
        if args.lossless:
            call_args.append("-lossless")
        call_args.append("-q")
        call_args.append("%u" % args.quality)
        call_args.append("-m")
        call_args.append("%u" % args.method)
        call_args.append("%s" % f)
        cnt += 1

    outfile = args.outfile
    if not outfile.lower().endswith(".webp"):
        # append output file extension if not already specified
        outfile += ".webp"
    if outfile.startswith("#dir/") or outfile.startswith("#dir\\") or outfile.startswith("#dir" + os.path.sep):
        # put in the same directory as the image directory, if the user wants to
        outfile = dir + os.path.sep + outfile[5:]

    call_args.append("-o")
    call_args.append("%s" % outfile)

    if args.verbose:
        s = "Calling: img2webp"
        cnt = 0
        for ar in call_args[1:]:
            s += " " + ar
            cnt += 1
            if cnt > 1000 and cnt < len(call_args):
                s += " ..."
                break
        print(s)

    if not args.verbose:
        print("Calling img2webp")

    p = subprocess.run(call_args)

    return 0

if __name__ == '__main__':
    sys.exit(main())
