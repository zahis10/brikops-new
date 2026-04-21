package com.brikops.app;

import android.os.Bundle;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.graphics.Insets;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        registerPlugin(SmsRetrieverPlugin.class);
        super.onCreate(savedInstanceState);

        ViewCompat.setOnApplyWindowInsetsListener(
            getWindow().getDecorView(), (view, windowInsets) -> {
                Insets insets = windowInsets.getInsets(
                    WindowInsetsCompat.Type.systemBars()
                );
                view.setPadding(
                    insets.left, insets.top,
                    insets.right, insets.bottom
                );
                return windowInsets;
            }
        );
    }
}
