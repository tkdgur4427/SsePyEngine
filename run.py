import math
import platform

# wrapper from calling c to python or vice versa
import cffi

# use python version raylib as well as raylib's native version
import pyray as rl
import raylib as nrl

import numpy as np

from sse import *

# retrieve ffi
ffi = cffi.FFI()


class Camera:
    def __init__(self):
        self.camera3d = rl.Camera3D()
        self.camera3d.position = rl.Vector3(2.0, 3.0, 5.0)
        self.camera3d.target = rl.Vector3(-0.5, 1.0, 0.0)
        self.camera3d.up = rl.Vector3(0.0, 1.0, 0.0)
        self.camera3d.fovy = 45.0
        self.camera3d.projection = rl.CAMERA_PERSPECTIVE
        self.azimuth = 0.0
        self.altitude = 0.4
        self.distance = 4.0
        self.offset = rl.vector3_zero()
        return

    def update(
        self,
        target,
        azimuth_delta,
        altitude_delta,
        offset_delta_x,
        offset_delta_y,
        mouse_wheel,
        dt,
    ):
        # theta(degree) of the sphere == azimuth
        # - it limits the increase of horizontal angle(phi): [0, 2*PI]
        self.azimuth = self.azimuth + 1.0 * dt * -azimuth_delta
        # phi(degree) of the sphere == altitude
        # - it limits the increase of vertical angle(phi): [0, PI]
        self.altitude = rl.clamp(
            self.altitude + 1.0 * dt * altitude_delta, 0.0, 0.4 * math.pi
        )
        # radius of the sphere == distance
        self.distance = rl.clamp(self.distance + 20.0 * dt * -mouse_wheel, 0.1, 100.0)

        rotation_azimuth = rl.quaternion_from_axis_angle(
            rl.Vector3(0, 1, 0), self.azimuth
        )
        position = rl.vector3_rotate_by_quaternion(
            rl.Vector3(0, 0, self.distance), rotation_azimuth
        )
        axis = rl.vector3_normalize(
            rl.vector3_cross_product(position, rl.Vector3(0, 1, 0))
        )

        rotation_altitude = rl.quaternion_from_axis_angle(axis, self.altitude)

        local_offset = rl.Vector3(dt * offset_delta_x, dt * -offset_delta_y, 0.0)
        local_offset = rl.vector3_rotate_by_quaternion(local_offset, rotation_azimuth)
        self.offset = rl.vector3_add(
            self.offset,
            rl.vector3_rotate_by_quaternion(local_offset, rotation_altitude),
        )

        camera_target = rl.vector3_add(self.offset, target)
        eye = rl.vector3_add(
            camera_target,
            rl.vector3_rotate_by_quaternion(position, rotation_altitude),
        )

        self.camera3d.position = eye
        self.camera3d.target = camera_target


class GBuffer:
    def __init__(self):
        # OpenGL framebuffer object id
        self.id = 0
        # color buffer attachment texture
        self.color = rl.Texture()
        # normal buffer attachment texture
        self.normal = rl.Texture()
        # depth buffer attachment texture
        self.depth = rl.Texture()


def load_gbuffer(width, height):
    target = GBuffer()
    target.id = rl.rl_load_framebuffer()
    assert target.id

    rl.rl_enable_framebuffer(target.id)

    target.color.id = rl.rl_load_texture(
        ffi.NULL, width, height, rl.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8, 1
    )
    target.color.width = width
    target.color.height = height
    target.color.format = rl.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8
    target.color.mipmaps = 1
    rl.rl_framebuffer_attach(
        target.id,
        target.color.id,
        rl.RL_ATTACHMENT_COLOR_CHANNEL0,
        rl.RL_ATTACHMENT_TEXTURE2D,
        0,
    )

    target.normal.id = rl.rl_load_texture(
        ffi.NULL, width, height, rl.PIXELFORMAT_UNCOMPRESSED_R16G16B16A16, 1
    )
    target.normal.width = width
    target.normal.height = height
    target.normal.format = rl.PIXELFORMAT_UNCOMPRESSED_R16G16B16A16
    target.normal.mipmaps = 1
    rl.rl_framebuffer_attach(
        target.id,
        target.normal.id,
        rl.RL_ATTACHMENT_COLOR_CHANNEL1,
        rl.RL_ATTACHMENT_TEXTURE2D,
        0,
    )

    target.depth.id = rl.rl_load_texture_depth(width, height, False)
    target.depth.width = width
    target.depth.height = height
    # DEPTH_COMPONENT_24BITS(?)
    target.depth.format = 19
    target.depth.mipmaps = 1
    rl.rl_framebuffer_attach(
        target.id,
        target.depth.id,
        rl.RL_ATTACHMENT_DEPTH,
        rl.RL_ATTACHMENT_TEXTURE2D,
        0,
    )

    # verification by the FBO(frame-buffer-object) with bound attachments
    assert rl.rl_framebuffer_complete(target.id)

    # disable FBO, return to default framebuffer
    rl.rl_disable_framebuffer()

    return target


def unload_gbuffer(target: GBuffer):
    if target.id > 0:
        rl.rl_unload_framebuffer(target.id)


def begin_gbuffer(target: GBuffer, camera: rl.Camera3D):

    rl.rl_draw_render_batch_active()

    # enable GBuffer FBO
    rl.rl_enable_framebuffer(target.id)

    # active MRT(multi-render-target)
    rl.rl_active_draw_buffers(2)

    # set viewport and RLGL internal frame buffer size
    nrl.rlViewport(0, 0, target.color.width, target.color.height)
    rl.rl_set_framebuffer_width(target.color.width)
    rl.rl_set_framebuffer_height(target.color.height)

    # clear background color:
    rl.clear_background(rl.BLACK)

    # switch to projection matrix
    rl.rl_matrix_mode(rl.RL_PROJECTION)

    # save previous matrix, which contains the settings for the 2d otho projection
    rl.rl_push_matrix()

    # reset current matrix
    rl.rl_load_identity()

    aspect = float(target.color.width) / float(target.color.height)

    # zNear and zFar values are important when computing depth buffer values:
    if camera.projection == rl.CAMERA_PERSPECTIVE:
        # setup perspective projection:
        top = rl.rl_get_cull_distance_near() * np.tan(camera.fovy * 0.5 * rl.DEG2RAD)
        right = top * aspect
        rl.rl_frustum(
            -right,
            right,
            -top,
            top,
            rl.rl_get_cull_distance_near(),
            rl.rl_get_cull_distance_far(),
        )

    elif camera.projection == rl.CAMERA_ORTHOGRAPHIC:
        # setup orthographic projection:
        top = camera.fovy / 2.0
        right = top * aspect
        rl.rl_ortho(
            -right,
            right,
            -top,
            top,
            rl.rl_get_cull_distance_near(),
            rl.rl_get_cull_distance_far(),
        )

    # switch back to modelview matrix
    rl.rl_matrix_mode(rl.RL_MODELVIEW)
    rl.rl_load_identity()

    # setup camera view
    mat_view = rl.matrix_look_at(camera.position, camera.target, camera.up)

    # multiply modelview matrix by view matrix (camera)
    mat_view_v = rl.matrix_to_float_v(mat_view)
    mat_view_v_ptr = ffi.addressof(mat_view_v.v, 0)
    rl.rl_mult_matrixf(mat_view_v_ptr)

    # enable depth test
    rl.rl_enable_depth_test()

    return


def end_gbuffer(width, height):

    # update and draw internal render batch
    rl.rl_draw_render_batch_active()

    # disable DEPTH_TEST:
    rl.rl_disable_depth_test()

    # deactivate MRT
    rl.rl_active_draw_buffers(1)

    # disable GBuffer FBO
    rl.rl_disable_framebuffer()

    # reset projection matrix
    rl.rl_matrix_mode(rl.RL_PROJECTION)
    rl.rl_pop_matrix()
    rl.rl_load_identity()
    rl.rl_ortho(0.0, float(width), float(height), 0.0, -1.0, 1.0)

    # reset model-view:
    rl.rl_matrix_mode(rl.RL_MODELVIEW)
    rl.rl_load_identity()

    return


class ShadowLight:
    def __init__(self):
        self.target = rl.vector3_zero()
        self.position = rl.vector3_zero()
        self.up = rl.Vector3(0.0, 1.0, 0.0)
        self.target = rl.vector3_zero()
        self.width = 0
        self.height = 0
        self.near = 0.0
        self.far = 1.0


def load_shadow_map(width, height):
    target = rl.RenderTexture()
    target.id = rl.rl_load_framebuffer()
    target.texture.width = width
    target.texture.height = height
    assert target.id != 0

    rl.rl_enable_framebuffer(target.id)

    target.depth.id = rl.rl_load_texture_depth(width, height, False)
    target.depth.width = width
    target.depth.height = height
    target.depth.format = 19
    target.depth.mipmaps = 1

    rl.rl_framebuffer_attach(
        target.id,
        target.depth.id,
        rl.RL_ATTACHMENT_DEPTH,
        rl.RL_ATTACHMENT_TEXTURE2D,
        0,
    )
    assert rl.rl_framebuffer_complete(target.id)

    rl.rl_disable_framebuffer()
    return target


def unload_shadow_map(target):
    if target.id > 0:
        rl.rl_unload_framebuffer(target.id)


def begin_shadow_map(target, shadow_light: ShadowLight):

    rl.begin_texture_mode(target)
    rl.clear_background(rl.WHITE)

    # update and draw internal render batch
    rl.rl_draw_render_batch_active()

    # switch to projection matrix:
    rl.rl_matrix_mode(rl.RL_PROJECTION)
    # save previous matrix, which contains the settings for the 2d ortho projection
    rl.rl_push_matrix()
    # reset current matrix(projection)
    rl.rl_load_identity()

    rl.rl_ortho(
        -shadow_light.width / 2,
        shadow_light.width / 2,
        -shadow_light.height / 2,
        shadow_light.height / 2,
        shadow_light.near,
        shadow_light.far,
    )

    rl.rl_matrix_mode(rl.RL_MODELVIEW)
    rl.rl_load_identity()

    # setup camera view:
    mat_view = rl.matrix_look_at(
        shadow_light.position, shadow_light.target, shadow_light.up
    )

    # multiply model-view matrix by view matrix (camera)
    mat_view_v = rl.matrix_to_float_v(mat_view)
    mat_view_v_ptr = ffi.addressof(mat_view_v.v, 0)
    rl.rl_mult_matrixf(mat_view_v_ptr)

    rl.rl_enable_depth_test()


def end_shadow_map():
    # update and draw internal render batch:
    rl.rl_draw_render_batch_active()

    # switch to projection matrix
    rl.rl_matrix_mode(rl.RL_PROJECTION)
    # restore previous matrix (projection) from matrix stack
    rl.rl_pop_matrix()

    # switch back to modelview matrix
    rl.rl_matrix_mode(rl.RL_MODELVIEW)
    rl.rl_load_identity()

    rl.rl_disable_depth_test()
    rl.end_texture_mode()


def set_shader_value_shader_map(shader: rl.Shader, loc_index: int, target):
    if loc_index > -1:
        rl.rl_enable_shader(shader.id)

        slot_ptr = ffi.new("int*")
        slot_ptr[0] = 10

        rl.rl_active_texture_slot(slot_ptr[0])
        rl.rl_enable_texture(target.depth.id)
        rl.rl_set_uniform(loc_index, slot_ptr, rl.SHADER_UNIFORM_INT, 1)


def run(use_renderdoc: bool = False):

    # cache renderdoc object
    rd = None
    if use_renderdoc:
        rd = RenderDocInstance.instance().rd

    # maximize log levels:
    rl.set_trace_log_level(rl.LOG_TRACE)

    # making sure if it is based on x64 architecture or not
    print(platform.architecture())

    # init window:
    screen_width = 1280
    screen_height = 720

    rl.set_config_flags(rl.FLAG_VSYNC_HINT)
    rl.init_window(screen_width, screen_height, b"SseEngine")
    rl.set_target_fps(60)

    # shaders:

    # *** shadow-shader
    shadow_shader = rl.load_shader(b"./shaders/shadow.vs", b"./shaders/shadow.fs")
    shadow_shader_light_clip_near_parameter = rl.get_shader_location(
        shadow_shader, b"LightClipNear"
    )
    shadow_shader_light_clip_far_parameter = rl.get_shader_location(
        shadow_shader, b"LightClipFar"
    )

    # *** basic-shader
    basic_shader = rl.load_shader(b"./shaders/basic.vs", b"./shaders/basic.fs")
    basic_shader_specularity_parameter = rl.get_shader_location(
        basic_shader, b"Specularity"
    )
    basic_shader_glossiness_parameter = rl.get_shader_location(
        basic_shader, b"Glossiness"
    )
    basic_shader_camera_clip_near_parameter = rl.get_shader_location(
        basic_shader, b"CameraClipNear"
    )
    basic_shader_camera_clip_far_parameter = rl.get_shader_location(
        basic_shader, b"CameraClipFar"
    )

    # *** lighting-shader
    lighting_shader = rl.load_shader(b"./shaders/quad.vs", b"./shaders/lighting.fs")
    lighting_shader_gbuffer_color_parameter = rl.get_shader_location(
        lighting_shader, b"GBufferColor"
    )
    lighting_shader_gbuffer_normal_parameter = rl.get_shader_location(
        lighting_shader, b"GBufferNormal"
    )
    lighting_shader_gbuffer_depth_parameter = rl.get_shader_location(
        lighting_shader, b"GBufferDepth"
    )
    lighting_shader_ssao_parameter = rl.get_shader_location(lighting_shader, b"SSAO")
    lighting_shader_camera_position_parameter = rl.get_shader_location(
        lighting_shader, b"CameraPosition"
    )
    lighting_shader_camera_inv_view_projection_parameter = rl.get_shader_location(
        lighting_shader, b"CameraInvViewProjection"
    )
    lighting_shader_light_direction_parameter = rl.get_shader_location(
        lighting_shader, b"LightDirection"
    )
    lighting_shader_sun_color_parameter = rl.get_shader_location(
        lighting_shader, b"SunColor"
    )
    lighting_shader_sun_intensity_parameter = rl.get_shader_location(
        lighting_shader, b"SunIntensity"
    )
    lighting_shader_sky_color_parameter = rl.get_shader_location(
        lighting_shader, b"SkyColor"
    )
    lighting_shader_sky_intensity_parameter = rl.get_shader_location(
        lighting_shader, b"SkyIntensity"
    )
    lighting_shader_ground_intensity_parameter = rl.get_shader_location(
        lighting_shader, b"GroundIntensity"
    )
    lighting_shader_ambient_intensity_parameter = rl.get_shader_location(
        lighting_shader, b"AmbientIntensity"
    )
    lighting_shader_exposure_parameter = rl.get_shader_location(
        lighting_shader, b"Exposure"
    )
    lighting_shader_camera_clip_near_parameter = rl.get_shader_location(
        lighting_shader, b"CameraClipNear"
    )
    lighting_shader_camera_clip_far_parameter = rl.get_shader_location(
        lighting_shader, b"CameraClipFar"
    )

    # *** ssao shader
    ssao_shader = rl.load_shader(b"./shaders/quad.vs", b"./shaders/ssao.fs")
    ssao_shader_gbuffer_depth_parameter = rl.get_shader_location(
        ssao_shader, b"GBufferDepth"
    )
    ssao_shader_gbuffer_normal_parameter = rl.get_shader_location(
        ssao_shader, b"GBufferNormal"
    )
    ssao_shader_camera_view_parameter = rl.get_shader_location(
        ssao_shader, b"CameraView"
    )
    ssao_shader_camera_projection_parameter = rl.get_shader_location(
        ssao_shader, b"CameraProjection"
    )
    ssao_shader_camera_inv_projection_parameter = rl.get_shader_location(
        ssao_shader, b"CameraInvProjection"
    )
    ssao_shader_camera_inv_view_projection_parameter = rl.get_shader_location(
        ssao_shader, b"CameraInvViewProjection"
    )
    ssao_shader_light_view_projection_parameter = rl.get_shader_location(
        ssao_shader, b"LightViewProjection"
    )
    ssao_shader_shadow_map_parameter = rl.get_shader_location(ssao_shader, b"ShadowMap")
    ssao_shader_shadow_inv_resolution_parameter = rl.get_shader_location(
        ssao_shader, b"ShadowInvResolution"
    )
    ssao_shader_camera_clip_near_parameter = rl.get_shader_location(
        ssao_shader, b"CameraClipNear"
    )
    ssao_shader_camera_clip_far_parameter = rl.get_shader_location(
        ssao_shader, b"CameraClipFar"
    )
    ssao_shader_light_clip_near_parameter = rl.get_shader_location(
        ssao_shader, b"LightClipNear"
    )
    ssao_shader_light_clip_far_parameter = rl.get_shader_location(
        ssao_shader, b"LightClipFar"
    )
    ssao_shader_light_direction_parameter = rl.get_shader_location(
        ssao_shader, b"LightDirection"
    )

    # *** blur shader
    blur_shader = rl.load_shader(b"./shaders/quad.vs", b"./shaders/blur.fs")
    blur_shader_gbuffer_normal_parameter = rl.get_shader_location(
        blur_shader, b"GBufferNormal"
    )
    blur_shader_gbuffer_depth_parameter = rl.get_shader_location(
        blur_shader, b"GBufferDepth"
    )
    blur_shader_input_texture_parameter = rl.get_shader_location(
        blur_shader, b"InputTexture"
    )
    blur_shader_camera_inv_projection_parameter = rl.get_shader_location(
        blur_shader, b"CameraInvProjection"
    )
    blur_shader_camera_clip_near_parameter = rl.get_shader_location(
        blur_shader, b"CameraClipNear"
    )
    blur_shader_camera_clip_far_parameter = rl.get_shader_location(
        blur_shader, b"CameraClipFar"
    )
    blur_shader_inv_texture_resolution_parameter = rl.get_shader_location(
        blur_shader, b"InvTextureResolution"
    )
    blur_shader_blur_direction_parameter = rl.get_shader_location(
        blur_shader, b"BlurDirection"
    )

    # *** fxaa shader
    fxaa_shader = rl.load_shader(b"./shaders/quad.vs", b"./shaders/fxaa.fs")
    fxaa_shader_input_texture_parameter = rl.get_shader_location(
        fxaa_shader, b"InputTexture"
    )
    fxaa_shader_inv_texture_resolution_parameter = rl.get_shader_location(
        fxaa_shader, b"InvTextureResolution"
    )

    # lights:
    light_direction = rl.vector3_normalize(rl.Vector3(0.35, -1.0, -0.35))

    # objects:
    ground_mesh = rl.gen_mesh_plane(20.0, 20.0, 10, 10)
    ground_model = rl.load_model_from_mesh(ground_mesh)
    ground_position = rl.Vector3(0.0, -0.01, 0.0)

    sphere_mesh = rl.gen_mesh_sphere(0.5, 32, 32)
    sphere_model = rl.load_model_from_mesh(sphere_mesh)
    sphere_position = rl.Vector3(0.0, 0.5, 0.0)

    # camera:
    camera = Camera()
    rl.rl_set_clip_planes(0.01, 50.0)

    # shadows:
    shadow_light = ShadowLight()
    shadow_light.target = rl.vector3_zero()
    shadow_light.position = rl.vector3_scale(light_direction, -5.0)
    shadow_light.up = rl.Vector3(0.0, 1.0, 0.0)
    shadow_light.width = 5.0
    shadow_light.height = 5.0
    shadow_light.near = 0.01
    shadow_light.far = 10.0

    shadow_width = 1024
    shadow_height = 1024
    shadow_inv_resolution = rl.Vector2(1.0 / shadow_width, 1.0 / shadow_height)
    shadow_map = load_shadow_map(shadow_width, shadow_height)

    # gbuffer and render textures:
    gbuffer = load_gbuffer(screen_width, screen_height)
    lighted = rl.load_render_texture(screen_width, screen_height)
    ssao_front = rl.load_render_texture(screen_width, screen_height)
    ssao_back = rl.load_render_texture(screen_width, screen_height)

    while not rl.window_should_close():

        # update camera:
        camera.update(
            rl.Vector3(0.0, 0.0, 0.0),
            (
                rl.get_mouse_delta().x
                if rl.is_key_down(rl.KEY_LEFT_CONTROL) and rl.is_mouse_button_down(0)
                else 0.0
            ),
            (
                rl.get_mouse_delta().y
                if rl.is_key_down(rl.KEY_LEFT_CONTROL) and rl.is_mouse_button_down(0)
                else 0.0
            ),
            (
                rl.get_mouse_delta().x
                if rl.is_key_down(rl.KEY_LEFT_CONTROL) and rl.is_mouse_button_down(1)
                else 0.0
            ),
            (
                rl.get_mouse_delta().y
                if rl.is_key_down(rl.KEY_LEFT_CONTROL) and rl.is_mouse_button_down(1)
                else 0.0
            ),
            rl.get_mouse_wheel_move(),
            rl.get_frame_time(),
        )

        if use_renderdoc:
            begin_renderdoc()

        # render(begin):
        rl.rl_disable_color_blend()
        rl.begin_drawing()

        # render shadow maps:
        begin_shadow_map(shadow_map, shadow_light)

        light_view_projection = rl.matrix_multiply(
            rl.rl_get_matrix_modelview(), rl.rl_get_matrix_projection()
        )
        light_clip_near = rl.rl_get_cull_distance_near()
        light_clip_far = rl.rl_get_cull_distance_far()
        light_clip_near_ptr = ffi.new("float*")
        light_clip_near_ptr[0] = light_clip_near
        light_clip_far_ptr = ffi.new("float*")
        light_clip_far_ptr[0] = light_clip_far

        rl.set_shader_value(
            shadow_shader,
            shadow_shader_light_clip_near_parameter,
            light_clip_near_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )
        rl.set_shader_value(
            shadow_shader,
            shadow_shader_light_clip_far_parameter,
            light_clip_far_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )

        ground_model.materials[0].shader = shadow_shader
        rl.draw_model(ground_model, ground_position, 1.0, rl.WHITE)

        sphere_model.materials[0].shader = shadow_shader
        rl.draw_model(sphere_model, sphere_position, 1.0, rl.WHITE)

        end_shadow_map()

        # render to gbuffer:
        begin_gbuffer(gbuffer, camera.camera3d)

        camera_view = rl.rl_get_matrix_modelview()
        camera_projection = rl.rl_get_matrix_projection()
        camera_inv_projection = rl.matrix_invert(camera_projection)
        camera_inv_view_projection = rl.matrix_invert(
            rl.matrix_multiply(camera_view, camera_projection)
        )
        camera_clip_near = rl.rl_get_cull_distance_near()
        camera_clip_far = rl.rl_get_cull_distance_far()
        camera_clip_near_ptr = ffi.new("float*", camera_clip_near)
        camera_clip_far_ptr = ffi.new("float*", camera_clip_far)
        specularity_ptr = ffi.new("float*", 0.5)
        glossiness_ptr = ffi.new("float*", 10.0)

        rl.set_shader_value(
            basic_shader,
            basic_shader_specularity_parameter,
            specularity_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )
        rl.set_shader_value(
            basic_shader,
            basic_shader_glossiness_parameter,
            glossiness_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )
        rl.set_shader_value(
            basic_shader,
            basic_shader_camera_clip_near_parameter,
            camera_clip_near_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )
        rl.set_shader_value(
            basic_shader,
            basic_shader_camera_clip_far_parameter,
            camera_clip_far_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )

        # draw ground model:
        ground_model.materials[0].shader = basic_shader
        rl.draw_model(ground_model, ground_position, 1.0, rl.Color(190, 190, 190, 255))

        sphere_model.materials[0].shader = basic_shader
        rl.draw_model(sphere_model, sphere_position, 1.0, rl.ORANGE)

        # end drawing to gbuffer
        end_gbuffer(screen_width, screen_height)

        # render ssao and shadows:
        rl.begin_texture_mode(ssao_front)

        rl.begin_shader_mode(ssao_shader)

        rl.set_shader_value_texture(
            ssao_shader, ssao_shader_gbuffer_normal_parameter, gbuffer.normal
        )
        rl.set_shader_value_texture(
            ssao_shader, ssao_shader_gbuffer_depth_parameter, gbuffer.depth
        )
        rl.set_shader_value_matrix(
            ssao_shader, ssao_shader_camera_view_parameter, camera_view
        )
        rl.set_shader_value_matrix(
            ssao_shader, ssao_shader_camera_projection_parameter, camera_projection
        )
        rl.set_shader_value_matrix(
            ssao_shader,
            ssao_shader_camera_inv_projection_parameter,
            camera_inv_projection,
        )
        rl.set_shader_value_matrix(
            ssao_shader,
            ssao_shader_camera_inv_view_projection_parameter,
            camera_inv_view_projection,
        )
        rl.set_shader_value_matrix(
            ssao_shader,
            ssao_shader_light_view_projection_parameter,
            light_view_projection,
        )
        set_shader_value_shader_map(
            ssao_shader, ssao_shader_shadow_map_parameter, shadow_map
        )

        rl.set_shader_value(
            ssao_shader,
            ssao_shader_shadow_inv_resolution_parameter,
            ffi.addressof(shadow_inv_resolution),
            rl.SHADER_UNIFORM_VEC2,
        )
        rl.set_shader_value(
            ssao_shader,
            ssao_shader_camera_clip_near_parameter,
            camera_clip_near_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )
        rl.set_shader_value(
            ssao_shader,
            ssao_shader_camera_clip_far_parameter,
            camera_clip_far_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )
        rl.set_shader_value(
            ssao_shader,
            ssao_shader_light_clip_near_parameter,
            light_clip_near_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )
        rl.set_shader_value(
            ssao_shader,
            ssao_shader_light_clip_far_parameter,
            light_clip_far_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )
        rl.set_shader_value(
            ssao_shader,
            ssao_shader_light_direction_parameter,
            ffi.addressof(light_direction),
            rl.SHADER_UNIFORM_VEC3,
        )

        rl.clear_background(rl.WHITE)

        rl.draw_texture_rec(
            ssao_front.texture,
            rl.Rectangle(0, 0, ssao_front.texture.width, -ssao_front.texture.height),
            rl.Vector2(0, 0),
            rl.WHITE,
        )

        rl.end_shader_mode()

        rl.end_texture_mode()

        # blur-horizontal
        rl.begin_texture_mode(ssao_back)
        rl.begin_shader_mode(blur_shader)

        blur_direction = rl.Vector2(1.0, 0.0)
        blur_inv_texture_resolution = rl.Vector2(
            1.0 / ssao_front.texture.width, 1.0 / ssao_front.texture.height
        )

        rl.set_shader_value_texture(
            blur_shader, blur_shader_gbuffer_normal_parameter, gbuffer.normal
        )
        rl.set_shader_value_texture(
            blur_shader, blur_shader_gbuffer_depth_parameter, gbuffer.depth
        )
        rl.set_shader_value_texture(
            blur_shader, blur_shader_input_texture_parameter, ssao_front.texture
        )
        rl.set_shader_value_matrix(
            blur_shader,
            blur_shader_camera_inv_projection_parameter,
            camera_inv_projection,
        )
        rl.set_shader_value(
            blur_shader,
            blur_shader_camera_clip_near_parameter,
            camera_clip_near_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )
        rl.set_shader_value(
            blur_shader,
            blur_shader_camera_clip_far_parameter,
            camera_clip_far_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )
        rl.set_shader_value(
            blur_shader,
            blur_shader_inv_texture_resolution_parameter,
            ffi.addressof(blur_inv_texture_resolution),
            rl.SHADER_UNIFORM_VEC2,
        )
        rl.set_shader_value(
            blur_shader,
            blur_shader_blur_direction_parameter,
            ffi.addressof(blur_direction),
            rl.SHADER_UNIFORM_VEC2,
        )

        rl.draw_texture_rec(
            ssao_back.texture,
            rl.Rectangle(0, 0, ssao_back.texture.width, -ssao_back.texture.height),
            rl.Vector2(0, 0),
            rl.WHITE,
        )

        rl.end_shader_mode()
        rl.end_texture_mode()

        # blur vertical:
        rl.begin_texture_mode(ssao_front)
        rl.begin_shader_mode(blur_shader)

        blur_direction = rl.Vector2(0.0, 1.0)

        rl.set_shader_value_texture(
            blur_shader, blur_shader_input_texture_parameter, ssao_back.texture
        )
        rl.set_shader_value(
            blur_shader,
            blur_shader_blur_direction_parameter,
            ffi.addressof(blur_direction),
            rl.SHADER_UNIFORM_VEC2,
        )

        rl.draw_texture_rec(
            ssao_front.texture,
            rl.Rectangle(0, 0, ssao_front.texture.width, -ssao_front.texture.height),
            rl.Vector2(0, 0),
            rl.WHITE,
        )

        rl.end_shader_mode()
        rl.end_texture_mode()

        # light gbuffer:
        rl.begin_texture_mode(lighted)

        rl.begin_shader_mode(lighting_shader)

        sun_color = rl.Vector3(253.0 / 255.0, 255.0 / 255.0, 232.0 / 255.0)
        sun_intensity_ptr = ffi.new("float*", 0.25)
        sky_color = rl.Vector3(174.0 / 255.0, 183.0 / 255.0, 190.0 / 255.0)
        sky_intensity_ptr = ffi.new("float*", 0.15)
        ground_intensity_ptr = ffi.new("float*", 0.1)
        ambient_intensity_ptr = ffi.new("float*", 1.0)
        exposure_ptr = ffi.new("float*", 0.9)

        rl.set_shader_value_texture(
            lighting_shader, lighting_shader_gbuffer_color_parameter, gbuffer.color
        )
        rl.set_shader_value_texture(
            lighting_shader, lighting_shader_gbuffer_normal_parameter, gbuffer.normal
        )
        rl.set_shader_value_texture(
            lighting_shader, lighting_shader_gbuffer_depth_parameter, gbuffer.depth
        )
        rl.set_shader_value_texture(
            lighting_shader, lighting_shader_ssao_parameter, ssao_front.texture
        )
        rl.set_shader_value(
            lighting_shader,
            lighting_shader_camera_position_parameter,
            ffi.addressof(camera.camera3d.position),
            rl.SHADER_UNIFORM_VEC3,
        )
        rl.set_shader_value_matrix(
            lighting_shader,
            lighting_shader_camera_inv_view_projection_parameter,
            camera_inv_projection,
        )
        rl.set_shader_value(
            lighting_shader,
            lighting_shader_light_direction_parameter,
            ffi.addressof(light_direction),
            rl.SHADER_UNIFORM_VEC3,
        )
        rl.set_shader_value(
            lighting_shader,
            lighting_shader_sun_color_parameter,
            ffi.addressof(sun_color),
            rl.SHADER_UNIFORM_VEC3,
        )
        rl.set_shader_value(
            lighting_shader,
            lighting_shader_sun_intensity_parameter,
            sun_intensity_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )
        rl.set_shader_value(
            lighting_shader,
            lighting_shader_sky_color_parameter,
            ffi.addressof(sky_color),
            rl.SHADER_UNIFORM_VEC3,
        )
        rl.set_shader_value(
            lighting_shader,
            lighting_shader_sky_intensity_parameter,
            sky_intensity_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )
        rl.set_shader_value(
            lighting_shader,
            lighting_shader_ground_intensity_parameter,
            ground_intensity_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )
        rl.set_shader_value(
            lighting_shader,
            lighting_shader_ambient_intensity_parameter,
            ambient_intensity_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )
        rl.set_shader_value(
            lighting_shader,
            lighting_shader_exposure_parameter,
            exposure_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )
        rl.set_shader_value(
            lighting_shader,
            lighting_shader_camera_clip_near_parameter,
            camera_clip_near_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )
        rl.set_shader_value(
            lighting_shader,
            lighting_shader_camera_clip_far_parameter,
            camera_clip_far_ptr,
            rl.SHADER_UNIFORM_FLOAT,
        )

        rl.clear_background(rl.RAYWHITE)

        rl.draw_texture_rec(
            gbuffer.color,
            rl.Rectangle(0, 0, gbuffer.color.width, -gbuffer.color.height),
            rl.Vector2(0, 0),
            rl.WHITE,
        )

        rl.end_shader_mode()

        rl.end_texture_mode()

        # render final with fxaa:
        rl.begin_shader_mode(fxaa_shader)

        fxaa_inv_texture_resolution = rl.Vector2(
            1.0 / lighted.texture.width, 1.0 / lighted.texture.height
        )

        rl.set_shader_value_texture(
            fxaa_shader, fxaa_shader_input_texture_parameter, lighted.texture
        )
        rl.set_shader_value(
            fxaa_shader,
            fxaa_shader_inv_texture_resolution_parameter,
            ffi.addressof(fxaa_inv_texture_resolution),
            rl.SHADER_UNIFORM_VEC2,
        )

        rl.draw_texture_rec(
            lighted.texture,
            rl.Rectangle(0, 0, lighted.texture.width, -lighted.texture.height),
            rl.Vector2(0, 0),
            rl.WHITE,
        )

        rl.end_shader_mode()

        # UI:
        rl.rl_enable_color_blend()
        rl.gui_group_box(rl.Rectangle(20, 10, 190, 180), b"Camera")
        rl.gui_label(rl.Rectangle(30, 20, 150, 20), b"Ctrl + Left Click - Rotate")
        rl.gui_label(rl.Rectangle(30, 40, 150, 20), b"Ctrl + Right Click - Pan")
        rl.gui_label(rl.Rectangle(30, 60, 150, 20), b"Mouse Scroll - Zoom")

        # render(end):
        rl.end_drawing()

        if use_renderdoc:
            end_renderdoc()

    # unload gbuffer and render textures:
    rl.unload_render_texture(lighted)
    unload_gbuffer(gbuffer)

    # unload shadow map
    unload_shadow_map(shadow_map)

    # unload models
    rl.unload_model(ground_model)

    # unload shader
    rl.unload_shader(shadow_shader)
    rl.unload_shader(basic_shader)
    rl.unload_shader(lighting_shader)

    rl.close_window()


def render_doc_test():

    rd = RenderDocInstance.instance().rd

    rl.init_window(1280, 720, b"RenderDoc Cap Test")
    rl.set_target_fps(60)

    while not rl.window_should_close():

        begin_renderdoc()

        rl.begin_drawing()
        rl.clear_background(rl.RAYWHITE)
        rl.draw_text(b"F8: trigger, F9: start, F10: end+open", 20, 20, 20, rl.BLACK)
        rl.end_drawing()

        end_renderdoc()


if __name__ == "__main__":
    use_renderdoc: bool = True
    run(use_renderdoc)
    # render_doc_test()
