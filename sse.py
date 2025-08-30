import pyray as rl

# renderdoc:
from pyRenderdocApp import load_render_doc


# singleton instance for sse
class SingletonInstance:
    __instance = None

    @classmethod
    def __get_instance(cls):
        return cls.__instance

    @classmethod
    def instance(cls, *args, **kwargs):
        cls.__instance = cls(*args, **kwargs)
        cls.instance = cls.__get_instance
        return cls.__instance


# renderdoc singleton
class RenderDocInstance(SingletonInstance):
    def __init__(self):
        # retrieve renderdoc instance
        self.rd = load_render_doc()

        # set default dump renderdoc path:
        self.rd.set_capture_file_path_template("./renderdoc/captures")

        self.is_renderdoc_capturing = False


def launch_renderdoc():
    rd = RenderDocInstance.instance().rd

    # if no renderdoc instance exists, open the renderdoc
    if not rd.is_target_control_connected():
        rd.launch_replay_ui(1, None)


def begin_renderdoc():
    rd = RenderDocInstance.instance().rd

    # capture only one-frame
    if rl.is_key_pressed(rl.KEY_F8):
        rd.trigger_capture()
        launch_renderdoc()

    # capture multiple frames
    if (
        rl.is_key_pressed(rl.KEY_F9)
        and not RenderDocInstance.instance().is_renderdoc_capturing
    ):
        RenderDocInstance.instance().is_renderdoc_capturing = True
        rd.start_frame_capture(None, None)


def end_renderdoc():
    rd = RenderDocInstance.instance().rd

    if (
        rl.is_key_pressed(rl.KEY_F10)
        and RenderDocInstance.instance().is_renderdoc_capturing
    ):
        # stop capturing
        rd.end_frame_capture(None, None)
        RenderDocInstance.instance().is_renderdoc_capturing = False

        # if no renderdoc instance exists, open the renderdoc
        launch_renderdoc()
