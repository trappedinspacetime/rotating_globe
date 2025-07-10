from pyray import *
from raylib import ffi
import datetime
import math

vertex_shader_code = """
#version 330
in vec3 vertexPosition;
in vec2 vertexTexCoord;
uniform mat4 mvp;
out vec2 fragTexCoord;
void main() {
    fragTexCoord = vertexTexCoord;
    gl_Position = mvp * vec4(vertexPosition, 1.0);
}
"""

fragment_shader_code = """
#version 330
const float PI = 3.14159265359;

uniform vec2 rotation;
uniform vec2 resolution;
uniform sampler2D texture0;
uniform float sunDeclination;
uniform float sunHourAngle;

in vec2 fragTexCoord;
out vec4 fragColor;

vec2 SphericalProjection(vec2 uv, vec2 rotation) {
    float x = uv.x * 2.0 - 1.0;
    float y = uv.y * 2.0 - 1.0;
    if (x*x + y*y > 1.0) {
        return vec2(-1.0);
    }
    float longitude = atan(x, sqrt(1.0 - x*x - y*y)) + rotation.x;
    float latitude = asin(y) + rotation.y;
    longitude = mod(longitude, 2.0 * PI);
    latitude = clamp(latitude, -PI/2.0, PI/2.0);
    return vec2(longitude / (2.0 * PI), (latitude / PI) + 0.5);
}

float CalculateLighting(vec2 sphericalUV) {
    float lon = sphericalUV.x * 2.0 * PI - PI;
    float lat = (sphericalUV.y - 0.5) * PI;
    vec3 sunDir = normalize(vec3(cos(sunHourAngle), sin(sunHourAngle), tan(sunDeclination)));
    vec3 normal = normalize(vec3(cos(lon) * cos(lat), sin(lon) * cos(lat), sin(lat)));
    float lighting = max(0.0, dot(normal, sunDir));
    return lighting;
}

void main() {
    vec2 uv = fragTexCoord;
    vec2 sphericalUV = SphericalProjection(uv, rotation);
    
    if (sphericalUV.x < 0.0 || sphericalUV.y < 0.0 || 
        sphericalUV.x > 1.0 || sphericalUV.y > 1.0) {
        fragColor = vec4(0.0, 0.0, 0.0, 0.0); // Küre dışı tamamen şeffaf
        return;
    }
    
    vec4 baseColor = texture(texture0, sphericalUV);
    float lightIntensity = CalculateLighting(sphericalUV);
    fragColor = vec4(baseColor.rgb * lightIntensity, 1.0); // Küre içi opak
}
"""

class ResourceManager:
    textures = {}
    def add_texture(self, name, path):
        self.textures[name] = load_texture(path.encode())
    def __unload__(self):
        for texture in self.textures.values():
            unload_texture(texture)
        self.textures.clear()

class Window:
    def __init__(self, width, height, title):
        set_config_flags(ConfigFlags.FLAG_VSYNC_HINT | ConfigFlags.FLAG_WINDOW_TRANSPARENT | ConfigFlags.FLAG_WINDOW_UNDECORATED)
        init_window(width, height, title.encode())
        set_window_position(100, 100)  # Başlangıç pozisyonu
        self.res = ResourceManager()
        self.res.add_texture("map", "map.png")
        self.renderer = load_render_texture(self.res.textures["map"].width, self.res.textures["map"].height)
        set_texture_filter(self.renderer.texture, TextureFilter.TEXTURE_FILTER_BILINEAR)
        self.camera = Camera2D(Vector2(width/2, height/2), Vector2(width/2, height/2), 0, 1.0)
        self.shader = load_shader_from_memory(vertex_shader_code.encode(), fragment_shader_code.encode())
        
        self.rot = Vector2(0, 0)
        self.update_shader_values()
        resolution = [width, height]
        resolution_ptr = ffi.new("float[2]", resolution)
        set_shader_value(self.shader, get_shader_location(self.shader, b"resolution"), resolution_ptr, ShaderUniformDataType.SHADER_UNIFORM_VEC2)

    def update_shader_values(self):
        rotation = [self.rot.x, self.rot.y]
        rotation_ptr = ffi.new("float[2]", rotation)
        set_shader_value(self.shader, get_shader_location(self.shader, b"rotation"), rotation_ptr, ShaderUniformDataType.SHADER_UNIFORM_VEC2)
        
        now = datetime.datetime.utcnow()
        day_of_year = now.timetuple().tm_yday
        hour = now.hour + now.minute / 60.0
        hour -= 1 # Yerel saat farkı, örneğin Türkiye için UTC+3
        
        sunDeclination = 23.5 * math.cos(2 * math.pi * (day_of_year - 172) / 365.25) * math.pi / 180.0
        sunHourAngle = -(hour - 12.0) * 15.0 * math.pi / 180.0
        
        set_shader_value(self.shader, get_shader_location(self.shader, b"sunDeclination"), ffi.new("float*", sunDeclination), ShaderUniformDataType.SHADER_UNIFORM_FLOAT)
        set_shader_value(self.shader, get_shader_location(self.shader, b"sunHourAngle"), ffi.new("float*", sunHourAngle), ShaderUniformDataType.SHADER_UNIFORM_FLOAT)

    def run(self):
        source_rect = Rectangle(0, 0, self.res.textures["map"].width, self.res.textures["map"].height)
        dest_rect = Rectangle(0, 0, self.res.textures["map"].width, self.res.textures["map"].height)
        origin = Vector2(0, 0)
        
        while not window_should_close():
            # Sol tuşla döndürme
            if is_mouse_button_down(MouseButton.MOUSE_BUTTON_LEFT):
                delta = get_mouse_delta()
                self.rot.x += delta.x * 0.01
                self.update_shader_values()

            # Sağ tuşla sürükleme
            if is_mouse_button_down(MouseButton.MOUSE_BUTTON_RIGHT):
                delta = get_mouse_delta()
                current_pos = get_window_position()
                set_window_position(int(current_pos.x + delta.x), int(current_pos.y + delta.y))

            # Zoom kontrolü
            if is_key_down(KeyboardKey.KEY_KP_ADD) or is_key_down(KeyboardKey.KEY_EQUAL):
                self.camera.zoom += 0.02
                self.camera.zoom = clamp(self.camera.zoom, 1.0, 5.0)
            elif is_key_down(KeyboardKey.KEY_KP_SUBTRACT) or is_key_down(KeyboardKey.KEY_MINUS):
                self.camera.zoom -= 0.02
                self.camera.zoom = clamp(self.camera.zoom, 1.0, 5.0)

            self.update_shader_values()

            begin_texture_mode(self.renderer)
            clear_background(Color(0, 0, 0, 0))  # Şeffaf arka plan
            draw_texture_pro(self.res.textures["map"], source_rect, dest_rect, origin, 0, WHITE)
            end_texture_mode()

            begin_drawing()
            clear_background(Color(0, 0, 0, 0))  # Şeffaf arka plan
            begin_shader_mode(self.shader)
            begin_mode_2d(self.camera)
            draw_texture_pro(self.renderer.texture, 
                           Rectangle(0, 0, self.renderer.texture.width, -self.renderer.texture.height),
                           Rectangle(0, 0, get_screen_width(), get_screen_height()),
                           origin, 0, WHITE)
            end_mode_2d()
            end_shader_mode()
            # FPS kaldırıldı, dekorasyon yok
            end_drawing()

    def __del__(self):
        close_window()
        unload_render_texture(self.renderer)
        unload_shader(self.shader)
        self.res.__unload__()

def main():
    window = Window(300, 270, "Dünya Widget")
    window.run()

main()
