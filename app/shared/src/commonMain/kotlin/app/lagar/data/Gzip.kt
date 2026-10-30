package app.lagar.data

/**
 * Decompresses a gzip file (RFC 1952) holding one member, with a plain inflate (RFC 1951) that runs the same
 * on Android, iOS and the web. The API serves documents this way when `index.json` says
 * `"docs_encoding": "gzip"` (docs/api.md). Throws [IllegalArgumentException] on malformed or corrupt data.
 */
internal object Gzip {
    private const val FLAG_HCRC = 0x02
    private const val FLAG_EXTRA = 0x04
    private const val FLAG_NAME = 0x08
    private const val FLAG_COMMENT = 0x10
    private const val HEADER_SIZE = 10
    private const val TRAILER_SIZE = 8
    private const val METHOD_DEFLATE = 8

    fun decompress(data: ByteArray): ByteArray {
        require(data.size >= HEADER_SIZE + TRAILER_SIZE) { "gzip data too short" }
        require(data.u8(0) == 0x1f && data.u8(1) == 0x8b && data.u8(2) == METHOD_DEFLATE) { "not gzip data" }
        val flags = data.u8(3)
        var pos = HEADER_SIZE
        if (flags and FLAG_EXTRA != 0) pos += 2 + data.u16(pos)
        if (flags and FLAG_NAME != 0) pos = data.afterZero(pos)
        if (flags and FLAG_COMMENT != 0) pos = data.afterZero(pos)
        if (flags and FLAG_HCRC != 0) pos += 2
        val inflater = Inflater(data, pos)
        val out = inflater.inflate()
        val end = inflater.bytePosition()
        require(end + TRAILER_SIZE <= data.size) { "gzip trailer missing" }
        require(data.u32(end) == crc32(out)) { "gzip checksum mismatch" }
        require(data.u32(end + 4) == out.size.toLong() and 0xffffffffL) { "gzip size mismatch" }
        return out
    }

    private fun ByteArray.u8(i: Int): Int = this[i].toInt() and 0xff

    private fun ByteArray.u16(i: Int): Int = u8(i) or (u8(i + 1) shl 8)

    private fun ByteArray.u32(i: Int): Long = (u16(i).toLong() or (u16(i + 2).toLong() shl 16))

    private fun ByteArray.afterZero(start: Int): Int {
        var i = start
        while (i < size && this[i] != 0.toByte()) i++
        require(i < size) { "gzip header truncated" }
        return i + 1
    }

    private val crcTable = IntArray(256) { n ->
        var c = n
        repeat(8) { c = if (c and 1 != 0) (c ushr 1) xor 0xEDB88320.toInt() else c ushr 1 }
        c
    }

    fun crc32(bytes: ByteArray): Long {
        var c = -1
        for (b in bytes) c = crcTable[(c xor b.toInt()) and 0xff] xor (c ushr 8)
        return c.inv().toLong() and 0xffffffffL
    }
}

/** A Huffman code as counts per code length and symbols in code order (the canonical code of RFC 1951). */
private class Huffman(lengths: IntArray, offset: Int, n: Int) {
    val counts = IntArray(MAX_BITS + 1)
    val symbols = IntArray(n)

    init {
        for (i in 0 until n) counts[lengths[offset + i]]++
        counts[0] = 0
        val next = IntArray(MAX_BITS + 2)
        for (len in 1..MAX_BITS) next[len + 1] = next[len] + counts[len]
        for (i in 0 until n) {
            val len = lengths[offset + i]
            if (len != 0) symbols[next[len]++] = i
        }
    }

    companion object {
        const val MAX_BITS = 15
    }
}

private class Inflater(private val data: ByteArray, private var pos: Int) {
    private var bitBuf = 0
    private var bitCount = 0
    private var out = ByteArray(maxOf(1024, (data.size - pos) * 4))
    private var outSize = 0

    fun inflate(): ByteArray {
        do {
            val last = bits(1)
            when (bits(2)) {
                0 -> stored()
                1 -> codes(FIXED_LENGTHS, FIXED_DISTANCES)
                2 -> dynamic()
                else -> throw IllegalArgumentException("invalid deflate block type")
            }
        } while (last == 0)
        return out.copyOf(outSize)
    }

    /** The first byte after the deflate stream (the final block ends on a bit, the trailer on a byte). */
    fun bytePosition(): Int = pos

    private fun bits(need: Int): Int {
        var value = bitBuf
        while (bitCount < need) {
            require(pos < data.size) { "deflate data truncated" }
            value = value or ((data[pos++].toInt() and 0xff) shl bitCount)
            bitCount += 8
        }
        bitBuf = value ushr need
        bitCount -= need
        return value and ((1 shl need) - 1)
    }

    private fun put(b: Byte) {
        if (outSize == out.size) out = out.copyOf(out.size * 2)
        out[outSize++] = b
    }

    private fun stored() {
        bitBuf = 0
        bitCount = 0
        require(pos + 4 <= data.size) { "deflate data truncated" }
        val len = (data[pos].toInt() and 0xff) or ((data[pos + 1].toInt() and 0xff) shl 8)
        val nlen = (data[pos + 2].toInt() and 0xff) or ((data[pos + 3].toInt() and 0xff) shl 8)
        require(len == nlen.inv() and 0xffff) { "invalid stored block length" }
        pos += 4
        require(pos + len <= data.size) { "deflate data truncated" }
        for (i in 0 until len) put(data[pos + i])
        pos += len
    }

    private fun decode(h: Huffman): Int {
        var code = 0
        var first = 0
        var index = 0
        for (len in 1..Huffman.MAX_BITS) {
            code = code or bits(1)
            val count = h.counts[len]
            if (code - count < first) return h.symbols[index + (code - first)]
            index += count
            first = (first + count) shl 1
            code = code shl 1
        }
        throw IllegalArgumentException("invalid Huffman code")
    }

    private fun codes(lengthCode: Huffman, distCode: Huffman) {
        while (true) {
            var symbol = decode(lengthCode)
            when {
                symbol < 256 -> put(symbol.toByte())
                symbol == 256 -> return
                else -> {
                    symbol -= 257
                    require(symbol < LENGTH_BASE.size) { "invalid length code" }
                    val len = LENGTH_BASE[symbol] + bits(LENGTH_EXTRA[symbol])
                    val d = decode(distCode)
                    require(d < DIST_BASE.size) { "invalid distance code" }
                    val dist = DIST_BASE[d] + bits(DIST_EXTRA[d])
                    require(dist <= outSize) { "distance too far back" }
                    repeat(len) { put(out[outSize - dist]) }
                }
            }
        }
    }

    private fun dynamic() {
        val nlen = bits(5) + 257
        val ndist = bits(5) + 1
        val ncode = bits(4) + 4
        require(nlen <= 286 && ndist <= 30) { "invalid dynamic block counts" }
        val lengths = IntArray(320)
        for (i in 0 until ncode) lengths[CODE_LENGTH_ORDER[i]] = bits(3)
        val lencode = Huffman(lengths, 0, 19)
        lengths.fill(0, 0, 19)
        var index = 0
        while (index < nlen + ndist) {
            val symbol = decode(lencode)
            if (symbol < 16) {
                lengths[index++] = symbol
                continue
            }
            var len = 0
            val repeat = when (symbol) {
                16 -> {
                    require(index > 0) { "repeat with no previous length" }
                    len = lengths[index - 1]
                    3 + bits(2)
                }
                17 -> 3 + bits(3)
                else -> 11 + bits(7)
            }
            require(index + repeat <= nlen + ndist) { "too many code lengths" }
            repeat(repeat) { lengths[index++] = len }
        }
        require(lengths[256] != 0) { "no end-of-block code" }
        codes(Huffman(lengths, 0, nlen), Huffman(lengths, nlen, ndist))
    }

    private companion object {
        val LENGTH_BASE = intArrayOf(
            3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195,
            227, 258,
        )
        val LENGTH_EXTRA = intArrayOf(0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0)
        val DIST_BASE = intArrayOf(
            1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073,
            4097, 6145, 8193, 12289, 16385, 24577,
        )
        val DIST_EXTRA = intArrayOf(
            0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13,
        )
        val CODE_LENGTH_ORDER = intArrayOf(16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15)

        val FIXED_LENGTHS = Huffman(
            IntArray(288) {
                when {
                    it < 144 -> 8
                    it < 256 -> 9
                    it < 280 -> 7
                    else -> 8
                }
            },
            0,
            288,
        )
        val FIXED_DISTANCES = Huffman(IntArray(30) { 5 }, 0, 30)
    }
}
