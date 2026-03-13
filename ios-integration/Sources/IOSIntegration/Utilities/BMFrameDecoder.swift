#if canImport(UIKit)
import UIKit

/// Decodes Flipper Zero `.bm` 1-bit-per-pixel bitmap frames into `UIImage`.
///
/// The `.bm` format stores each row as a sequence of bytes; each bit encodes
/// one pixel (MSB first, 1 = white, 0 = black).  Rows are padded to the next
/// full byte boundary.  The file contains `width × height` bits laid out row
/// by row.
public enum BMFrameDecoder {

    // MARK: - Public

    /// Decodes raw `.bm` data into a `UIImage`.
    ///
    /// - Parameters:
    ///   - data: Raw bytes of the `.bm` file.
    ///   - width: Canvas width in pixels (e.g. 128 for a standard Flipper display).
    ///   - height: Canvas height in pixels (e.g. 64 for a standard Flipper display).
    /// - Returns: A `UIImage` if decoding succeeded, otherwise `nil`.
    public static func decode(data: Data, width: Int, height: Int) -> UIImage? {
        guard width > 0, height > 0 else { return nil }

        let bytesPerRow = (width + 7) / 8           // ceil(width / 8)
        let requiredBytes = bytesPerRow * height
        guard data.count >= requiredBytes else { return nil }

        // Build an RGBA pixel buffer (4 bytes per pixel)
        var pixels = [UInt8](repeating: 255, count: width * height * 4)

        for row in 0..<height {
            for col in 0..<width {
                let byteIndex  = row * bytesPerRow + col / 8
                let bitIndex   = 7 - (col % 8)      // MSB first
                let bit        = (data[byteIndex] >> bitIndex) & 1
                let pixelIndex = (row * width + col) * 4
                let value: UInt8 = bit == 1 ? 255 : 0
                pixels[pixelIndex]     = value  // R
                pixels[pixelIndex + 1] = value  // G
                pixels[pixelIndex + 2] = value  // B
                pixels[pixelIndex + 3] = 255    // A (fully opaque)
            }
        }

        return makeImage(pixels: pixels, width: width, height: height)
    }

    /// Decodes a sequence of `.bm` frames into an array of `UIImage`.
    public static func decodeFrames(data: Data, width: Int, height: Int, frameCount: Int) -> [UIImage] {
        let bytesPerRow   = (width + 7) / 8
        let bytesPerFrame = bytesPerRow * height
        guard frameCount > 0, data.count >= bytesPerFrame * frameCount else { return [] }

        return (0..<frameCount).compactMap { frame in
            let start = frame * bytesPerFrame
            let slice = data[start..<(start + bytesPerFrame)]
            return decode(data: Data(slice), width: width, height: height)
        }
    }

    // MARK: - Private

    private static func makeImage(pixels: [UInt8], width: Int, height: Int) -> UIImage? {
        let colorSpace  = CGColorSpaceCreateDeviceRGB()
        let bitmapInfo  = CGBitmapInfo(rawValue: CGImageAlphaInfo.premultipliedLast.rawValue)
        let bytesPerRow = width * 4

        guard let context = CGContext(
            data: UnsafeMutableRawPointer(mutating: pixels),
            width: width,
            height: height,
            bitsPerComponent: 8,
            bytesPerRow: bytesPerRow,
            space: colorSpace,
            bitmapInfo: bitmapInfo.rawValue
        ), let cgImage = context.makeImage() else {
            return nil
        }

        return UIImage(cgImage: cgImage)
    }
}
#endif
