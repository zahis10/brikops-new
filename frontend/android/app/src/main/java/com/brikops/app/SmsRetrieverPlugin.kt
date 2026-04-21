package com.brikops.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.Build
import androidx.core.content.ContextCompat
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.CapacitorPlugin
import com.google.android.gms.auth.api.phone.SmsRetriever
import com.google.android.gms.common.api.CommonStatusCodes
import com.google.android.gms.common.api.Status

/**
 * In-house Capacitor plugin wrapping Google Play Services SMS Retriever API.
 *
 * SECURITY: Does NOT request READ_SMS or RECEIVE_SMS permissions.
 * Google Play Services delivers ONLY messages whose body ends with the
 * app's 11-char hash (derived from the release keystore SHA-256), so the
 * app cannot read any other SMS on the device.
 *
 * USAGE FROM JS:
 *   import { SmsRetriever } from '../native/SmsRetriever';
 *   await SmsRetriever.start();
 *   SmsRetriever.addListener('smsReceived', ({ message }) => { ... });
 *   await SmsRetriever.stop();
 */
@CapacitorPlugin(name = "SmsRetriever")
class SmsRetrieverPlugin : Plugin() {

    private var receiver: BroadcastReceiver? = null

    @PluginMethod
    fun start(call: PluginCall) {
        try {
            registerReceiverIfNeeded()
            val client = SmsRetriever.getClient(context)
            client.startSmsRetriever()
                .addOnSuccessListener {
                    val ret = JSObject()
                    ret.put("started", true)
                    call.resolve(ret)
                }
                .addOnFailureListener { e ->
                    call.reject("SMS_RETRIEVER_START_FAILED", e)
                }
        } catch (e: Exception) {
            call.reject("SMS_RETRIEVER_EXCEPTION", e)
        }
    }

    @PluginMethod
    fun stop(call: PluginCall) {
        unregisterReceiverIfNeeded()
        val ret = JSObject()
        ret.put("stopped", true)
        call.resolve(ret)
    }

    private fun registerReceiverIfNeeded() {
        if (receiver != null) return
        receiver = object : BroadcastReceiver() {
            override fun onReceive(ctx: Context, intent: Intent) {
                if (intent.action != SmsRetriever.SMS_RETRIEVED_ACTION) return
                val extras = intent.extras ?: return
                val status = extras.get(SmsRetriever.EXTRA_STATUS) as? Status ?: return
                when (status.statusCode) {
                    CommonStatusCodes.SUCCESS -> {
                        val message = extras.getString(SmsRetriever.EXTRA_SMS_MESSAGE) ?: ""
                        val payload = JSObject()
                        payload.put("message", message)
                        notifyListeners("smsReceived", payload)
                    }
                    CommonStatusCodes.TIMEOUT -> {
                        val payload = JSObject()
                        payload.put("error", "timeout")
                        notifyListeners("smsTimeout", payload)
                    }
                }
            }
        }
        val filter = IntentFilter(SmsRetriever.SMS_RETRIEVED_ACTION)
        // SEND_PERMISSION ensures only Google Play Services can deliver this broadcast.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            ContextCompat.registerReceiver(
                context,
                receiver,
                filter,
                SmsRetriever.SEND_PERMISSION,
                null,
                ContextCompat.RECEIVER_EXPORTED
            )
        } else {
            @Suppress("UnspecifiedRegisterReceiverFlag")
            context.registerReceiver(receiver, filter, SmsRetriever.SEND_PERMISSION, null)
        }
    }

    private fun unregisterReceiverIfNeeded() {
        receiver?.let {
            try {
                context.unregisterReceiver(it)
            } catch (_: IllegalArgumentException) {
                // Receiver was not registered; ignore.
            }
        }
        receiver = null
    }

    override fun handleOnDestroy() {
        unregisterReceiverIfNeeded()
        super.handleOnDestroy()
    }
}
