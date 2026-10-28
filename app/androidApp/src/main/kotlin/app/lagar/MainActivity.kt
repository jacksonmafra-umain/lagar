package app.lagar

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import app.lagar.data.DataSourceConfig

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        // Debug builds read the API served from the host machine (the emulator's alias for it);
        // release builds use the bundled sample.
        setContent { App(DataSourceConfig(useSample = !BuildConfig.DEBUG, baseUrl = "http://10.0.2.2:8000/api/v1/")) }
    }
}
